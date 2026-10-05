from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.demand import run_demand_agent
from app.agents.inventory import run_inventory_agent
from app.agents.risk import run_risk_agent
from app.agents.route import run_route_agent
from app.agents.schemas import (
    AgentBundle,
    DemandResult,
    InventoryResult,
    RiskResult,
    RouteResult,
    SupplierResult,
)
from app.agents.supplier import run_supplier_agent
from app.core.config import settings
from app.core.provenance import EvidenceHit
from app.graph.state import GraphState
from app.hitl.constraints import HumanConstraint
from app.live.feed import fuel_multiplier
from app.llm.factory import Intent, narrate_plan, parse_intent
from app.optimization.solver import solve_bundle
from app.rag.search import search
from app.scenarios.engine import (
    combine_patches,
    constraints_to_patch,
    merge_constraints,
    scenario_from_text,
)
from app.validation.validator import validate_plan
from app.whatif.engine import WhatIfPatch


def _trace(state: GraphState, msg: str) -> list[str]:
    return list(state.get("trace") or []) + [msg]


def parse_node(state: GraphState) -> dict[str, Any]:
    intent = parse_intent(state["query"])
    trace = _trace(state, f"parsed intent product={intent.product_query} qty={intent.quantity}")
    if intent.llm_warning:
        trace = trace + [f"llm warning: {intent.llm_warning}"]
    if intent.constraints:
        trace = trace + [f"nl constraints: {len(intent.constraints)}"]
    return {
        "intent": intent.model_dump(),
        "replan_count": state.get("replan_count") or 0,
        "review_status": state.get("review_status") or "pending_review",
        "trace": trace,
    }


def supervisor_node(state: GraphState) -> dict[str, Any]:
    q = (state.get("query") or "").lower()
    needed = ["demand", "supplier", "route", "inventory", "risk"]
    if "inventory" in q and "supplier" not in q and "route" not in q and "cost" not in q:
        needed = ["demand", "inventory", "risk"]
    return {"agents_needed": needed, "trace": _trace(state, f"supervisor selected {needed}")}


def rag_node(db: Session, state: GraphState) -> dict[str, Any]:
    intent = Intent.model_validate(state["intent"])
    query = f"{state['query']} {intent.product_query} sourcing policy safety stock disruption risk fuel"
    hits = search(db, query, k=6)
    return {
        "evidence": [h.model_dump() for h in hits],
        "trace": _trace(state, f"rag retrieved {len(hits)} chunks"),
    }


def _stored_constraints(state: GraphState) -> list[HumanConstraint]:
    raw = state.get("human_constraints") or []
    return [HumanConstraint.model_validate(item) for item in raw]


def _active_scenario(state: GraphState, intent: Intent):
    inferred = scenario_from_text("")
    inferred.constraints = list(intent.constraints)
    inferred.patch = constraints_to_patch(intent.constraints, label="query scenario" if intent.constraints else "baseline")
    explicit = WhatIfPatch.model_validate(state["patch"]) if state.get("patch") else None
    feedback = _stored_constraints(state)
    constraints = merge_constraints(inferred.constraints, feedback)
    patch = combine_patches(explicit, constraints_to_patch(constraints, label=(explicit.label if explicit else inferred.patch.label)))
    narrative = patch.label or "baseline"
    return patch, constraints, narrative


def specialists_node(db: Session, state: GraphState) -> dict[str, Any]:
    intent = Intent.model_validate(state["intent"])
    patch, constraints, narrative = _active_scenario(state, intent)
    for item in constraints:
        if item.kind == "max_lead_time_days" and item.value is not None:
            intent.lead_time_days_max = min(intent.safe_lead_time, int(item.value))
    demand = run_demand_agent(db, intent)
    if patch.demand_multiplier != 1.0:
        demand.demand_to_meet = int(round(demand.demand_to_meet * patch.demand_multiplier))
        demand.notes.append(f"What-if demand multiplier {patch.demand_multiplier}")
    failed = set(patch.failed_supplier_codes)
    failed.update(c.code for c in constraints if c.kind == "exclude_supplier" and c.code)
    suppliers = run_supplier_agent(
        db,
        intent,
        demand,
        failed_supplier_codes=failed,
        price_multiplier=patch.price_multiplier,
    )
    min_reliability = max(
        (c.value for c in constraints if c.kind == "min_reliability" and c.value is not None),
        default=None,
    )
    if min_reliability is not None:
        for offer in suppliers.offers:
            if offer.reliability_score < min_reliability:
                offer.eligible = False
                offer.reasons.append(f"reliability below human minimum {min_reliability}")
    disrupted = set(patch.disrupted_route_codes)
    disrupted.update(c.code for c in constraints if c.kind == "exclude_route" and c.code)
    routes = run_route_agent(
        db,
        suppliers,
        disrupted_route_codes=disrupted,
        fuel_multiplier=round(patch.fuel_multiplier * fuel_multiplier(db), 4),
    )
    inventory = run_inventory_agent(db, demand, inventory_factor=patch.inventory_factor)
    risk = run_risk_agent(db, suppliers, routes, scenario_label=narrative)
    needed = set(state.get("agents_needed") or ["demand", "supplier", "route", "inventory", "risk"])
    return {
        "demand": demand.model_dump(),
        "suppliers": suppliers.model_dump(),
        "routes": routes.model_dump(),
        "inventory": inventory.model_dump(),
        "risk": risk.model_dump(),
        "patch": patch.model_dump(),
        "human_constraints": [c.model_dump() for c in constraints],
        "scenario": {"label": narrative, "patch": patch.model_dump(), "narrative": narrative},
        "trace": _trace(state, f"specialist agents completed ({sorted(needed)}) scenario={narrative}"),
    }


def solve_node(state: GraphState) -> dict[str, Any]:
    bundle = AgentBundle(
        demand=DemandResult.model_validate(state["demand"]),
        suppliers=SupplierResult.model_validate(state["suppliers"]),
        routes=RouteResult.model_validate(state["routes"]),
        inventory=InventoryResult.model_validate(state["inventory"]),
        risk=RiskResult.model_validate(state["risk"]),
    )
    intent = Intent.model_validate(state["intent"])
    result = solve_bundle(
        bundle,
        enforce_low_risk=intent.low_risk,
        human_constraints=state.get("human_constraints") or [],
    )
    return {
        "solver": result.model_dump(),
        "trace": _trace(state, f"solver status={result.status} cost={result.total_cost}"),
    }


def _evidence_hits(state: GraphState) -> list[EvidenceHit]:
    hits: list[EvidenceHit] = []
    for item in state.get("evidence") or []:
        if isinstance(item, EvidenceHit):
            hits.append(item)
            continue
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        payload["document_id"] = str(payload.get("document_id") or payload.get("id") or "")
        payload.setdefault("title", "Untitled")
        payload.setdefault("snippet", str(payload.get("content") or "")[:420])
        payload.setdefault("score", 0.0)
        try:
            hits.append(EvidenceHit.model_validate(payload))
        except Exception:
            continue
    return hits


def validate_node(state: GraphState) -> dict[str, Any]:
    evidence = _evidence_hits(state)
    bundle = AgentBundle(
        demand=DemandResult.model_validate(state["demand"]),
        suppliers=SupplierResult.model_validate(state["suppliers"]),
        routes=RouteResult.model_validate(state["routes"]),
        inventory=InventoryResult.model_validate(state["inventory"]),
        risk=RiskResult.model_validate(state["risk"]),
        evidence=evidence,
    )
    from app.optimization.solver import SolverResult

    solver = SolverResult.model_validate(state["solver"])
    report = validate_plan(bundle, solver)
    report["evidence_count"] = len(evidence)
    if state.get("evidence") and not evidence:
        report["issues"] = list(report.get("issues") or []) + ["RAG evidence payload could not be parsed"]
    return {
        "validation": report,
        "evidence": [hit.model_dump() for hit in evidence] or list(state.get("evidence") or []),
        "trace": _trace(state, f"validation ok={report['ok']} evidence={len(evidence)}"),
    }


def hitl_node(state: GraphState) -> dict[str, Any]:
    status = state.get("review_status") or "pending_review"
    constraints = state.get("human_constraints") or []
    return {
        "review_status": status,
        "trace": _trace(
            state,
            f"human review checkpoint status={status} constraints={len(constraints)}",
        ),
    }


def should_replan(state: GraphState) -> str:
    report = state.get("validation") or {}
    count = int(state.get("replan_count") or 0)
    if not report.get("ok") and count < settings.max_replan:
        return "replan"
    return "explain"


def replan_node(state: GraphState) -> dict[str, Any]:
    intent = dict(state.get("intent") or {})
    intent["lead_time_days_max"] = int(intent.get("lead_time_days_max") or 31) + 15
    intent["low_risk"] = False
    return {
        "intent": intent,
        "replan_count": int(state.get("replan_count") or 0) + 1,
        "trace": _trace(state, "replan: relaxed lead time and low-risk hard constraints"),
    }


def explain_node(state: GraphState) -> dict[str, Any]:
    demand = state.get("demand") or {}
    solver = state.get("solver") or {}
    risk = state.get("risk") or {}
    inv = state.get("inventory") or {}
    allocs = solver.get("allocations") or []
    by_sup: dict[str, dict[str, Any]] = {}
    for a in allocs:
        rec = by_sup.setdefault(
            a["supplier_code"],
            {"supplier_code": a["supplier_code"], "supplier_name": a["supplier_name"], "units": 0, "cost": 0.0},
        )
        rec["units"] += a["quantity"]
        rec["cost"] += a["line_cost"]

    lines = [
        f"Demand to meet: {demand.get('demand_to_meet')} units of {demand.get('product_name')} "
        f"(forecast {demand.get('forecast_units')} via {demand.get('forecast_method')}).",
        f"Net procurement after inventory: {inv.get('net_requirement')} units.",
        f"Solver {solver.get('status')} with total cost {solver.get('total_cost')} "
        f"(procurement {solver.get('procurement_cost')} + transport {solver.get('transport_cost')}).",
        f"Longest fulfillment time {solver.get('delivery_time_hours')} hours. "
        f"Composite risk score {risk.get('score')}.",
    ]
    for rec in by_sup.values():
        lines.append(f"{rec['supplier_code']} ({rec['supplier_name']}) → {rec['units']} units.")
    if allocs:
        top_routes = sorted(allocs, key=lambda a: -a["quantity"])[:4]
        lines.append(
            "Best routes: "
            + "; ".join(f"{a['route_code']} {a['mode']} → {a['warehouse_code']} ({a['quantity']})" for a in top_routes)
        )
    evidence = state.get("evidence") or []
    if evidence:
        lines.append("Evidence used: " + "; ".join(e.get("title", "") for e in evidence[:4]))
    constraints = state.get("human_constraints") or []
    if constraints:
        lines.append(
            "Human constraints: "
            + "; ".join(c.get("raw") or c.get("kind", "") for c in constraints[:6])
        )
    scenario = state.get("scenario") or {}
    if scenario.get("label") and scenario.get("label") not in {"baseline", "query scenario"}:
        lines.append(f"Scenario applied: {scenario.get('label')}.")
    lines.append(
        "Reason: allocation quantities come from the OR-Tools model using database prices, "
        "capacities, lead times and route costs. The LLM only parsed the request and wrote this explanation."
    )
    facts = {
        "product_name": demand.get("product_name"),
        "forecast_units": demand.get("forecast_units"),
        "demand_to_meet": demand.get("demand_to_meet"),
        "net_requirement": inv.get("net_requirement"),
        "status": solver.get("status"),
        "total_cost": solver.get("total_cost"),
        "procurement_cost": solver.get("procurement_cost"),
        "transport_cost": solver.get("transport_cost"),
        "delivery_time_hours": solver.get("delivery_time_hours"),
        "risk_score": risk.get("score"),
        "suppliers": list(by_sup.values()),
        "routes": [
            {
                "route_code": row.get("route_code"),
                "warehouse_code": row.get("warehouse_code"),
                "mode": row.get("mode"),
                "quantity": row.get("quantity"),
            }
            for row in allocs[:6]
        ],
        "inventory_available": inv.get("total_available"),
        "request": state.get("query"),
    }
    narrative = narrate_plan(
        state.get("query") or "",
        facts,
        evidence,
        list(state.get("trace") or []) + lines,
    )
    relevance = {item["title"]: item["relevance"] for item in narrative.get("evidence") or []}
    explained_evidence = []
    for item in evidence:
        row = dict(item)
        row["relevance"] = relevance.get(row.get("title") or "", row.get("snippet"))
        explained_evidence.append(row)
    rec = {
        "summary": narrative.get("summary") or " ".join(lines[:3]),
        "reason": narrative.get("reason") or "\n".join(lines),
        "kpi_note": narrative.get("kpi_note") or "",
        "allocation_note": narrative.get("allocation_note") or "",
        "routes_note": narrative.get("routes_note") or "",
        "inventory_note": narrative.get("inventory_note") or "",
        "writer": narrative.get("writer") or "",
        "supplier_allocation": list(by_sup.values()),
        "routes": allocs,
        "forecast_units": demand.get("forecast_units"),
        "demand_to_meet": demand.get("demand_to_meet"),
        "net_requirement": inv.get("net_requirement"),
        "total_cost": solver.get("total_cost"),
        "delivery_time_hours": solver.get("delivery_time_hours"),
        "risk_score": risk.get("score"),
        "optimization_status": solver.get("status"),
        "data_disclaimer": "Demo only. Separate sources: database facts, forecast model, agent eligibility, solver quantities.",
    }
    return {
        "recommendation": rec,
        "evidence": explained_evidence,
        "trace": list(narrative.get("trace") or _trace(state, "explanation composed")),
    }

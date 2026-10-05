from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DecisionRun
from app.graph.graph import run_pipeline
from app.live.feed import tick
from app.whatif.engine import delivery_hours


def persist_run(
    db: Session,
    query: str,
    state: dict[str, Any],
    parent_run_id: int | None = None,
    extra: dict | None = None,
    human_feedback: str | None = None,
) -> DecisionRun:
    rec = state.get("recommendation") or {}
    payload = {
        "intent": state.get("intent"),
        "demand": state.get("demand"),
        "suppliers": state.get("suppliers"),
        "routes": state.get("routes"),
        "inventory": state.get("inventory"),
        "risk": state.get("risk"),
        "solver": state.get("solver"),
        "validation": state.get("validation"),
        "recommendation": rec,
        "evidence": state.get("evidence"),
        "trace": state.get("trace"),
        "patch": state.get("patch"),
        "human_constraints": state.get("human_constraints") or [],
        "scenario": state.get("scenario"),
        "review_status": state.get("review_status") or "pending_review",
        **(extra or {}),
    }
    intent = state.get("intent") or {}
    run = DecisionRun(
        query=query,
        status=(state.get("solver") or {}).get("status") or "completed",
        request_json={"query": query, "patch": state.get("patch")},
        result_json=payload,
        parent_run_id=parent_run_id,
        review_status=state.get("review_status") or "pending_review",
        human_feedback=human_feedback,
        human_constraints=state.get("human_constraints") or [],
        llm_warning=intent.get("llm_warning"),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def to_response(run: DecisionRun, what_if: dict | None = None) -> dict[str, Any]:
    r = run.result_json or {}
    rec = r.get("recommendation") or {}
    solver = r.get("solver") or {}
    demand = r.get("demand") or {}
    inv = r.get("inventory") or {}
    risk = r.get("risk") or {}
    return {
        "run_id": run.id,
        "query": run.query,
        "demand_forecast": {
            "product": demand.get("product_name"),
            "sku": demand.get("product_sku"),
            "forecast_units": demand.get("forecast_units"),
            "method": demand.get("forecast_method"),
            "history_months": demand.get("history_months"),
            "history": demand.get("history"),
            "requested_quantity": demand.get("requested_quantity"),
            "demand_to_meet": demand.get("demand_to_meet"),
            "provenance": demand.get("provenance"),
        },
        "supplier_allocation": rec.get("supplier_allocation") or [],
        "routes": rec.get("routes") or solver.get("allocations") or [],
        "inventory_plan": {
            "rows": inv.get("rows"),
            "total_available": inv.get("total_available"),
            "total_safety_stock": inv.get("total_safety_stock"),
            "net_requirement": inv.get("net_requirement"),
            "notes": inv.get("notes"),
            "provenance": inv.get("provenance"),
        },
        "total_cost": rec.get("total_cost") if rec.get("total_cost") is not None else solver.get("total_cost"),
        "delivery_time_hours": delivery_hours(rec, solver),
        "risk_score": rec.get("risk_score") if rec.get("risk_score") is not None else risk.get("score"),
        "optimization_status": rec.get("optimization_status") or solver.get("status"),
        "retrieved_evidence": r.get("evidence") or [],
        "explainable_recommendation": rec,
        "agent_trace": r.get("trace") or [],
        "validation": r.get("validation") or {},
        "what_if": what_if,
        "review_status": run.review_status or r.get("review_status") or "pending_review",
        "human_feedback": run.human_feedback,
        "human_constraints": run.human_constraints or r.get("human_constraints") or [],
        "llm_warning": run.llm_warning or (r.get("intent") or {}).get("llm_warning"),
        "scenario": r.get("scenario"),
        "data_as_of": (r.get("live") or {}).get("data_as_of"),
        "live": r.get("live"),
        "data_disclaimer": rec.get("data_disclaimer")
        or "SYNTHETIC DATA — for demo only.",
    }


def execute_decision(
    db: Session,
    query: str,
    patch: dict | None = None,
    parent_id: int | None = None,
    human_constraints: list | None = None,
    review_status: str = "pending_review",
    human_feedback: str | None = None,
) -> DecisionRun:
    live = tick(db)
    state = run_pipeline(
        db,
        query,
        patch=patch,
        human_constraints=human_constraints,
        review_status=review_status,
    )
    return persist_run(
        db,
        query,
        dict(state),
        parent_run_id=parent_id,
        human_feedback=human_feedback,
        extra={"live": live},
    )

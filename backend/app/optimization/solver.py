from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.schemas import AgentBundle, RouteOption, SupplierOffer
from app.core.config import settings
from app.hitl.constraints import HumanConstraint


class Allocation(BaseModel):
    supplier_code: str
    supplier_name: str
    warehouse_code: str
    route_code: str
    mode: str
    quantity: int
    unit_price: float
    transport_cost_per_unit: float
    line_cost: float
    lead_time_days: int
    transit_hours: float
    reliability_score: float


class SolverResult(BaseModel):
    status: str
    total_cost: float
    procurement_cost: float
    transport_cost: float
    risk_penalty_cost: float
    delivery_time_hours: float
    allocations: list[Allocation] = Field(default_factory=list)
    unmet_demand: int = 0
    objective_notes: list[str] = Field(default_factory=list)
    infeasibility: str | None = None


def _solver():
    from ortools.linear_solver import pywraplp

    for name in ("CBC_MIXED_INTEGER_PROGRAMMING", "SCIP", "CBC", "SAT"):
        try:
            s = pywraplp.Solver.CreateSolver(name)
            if s:
                return s, name
        except Exception:
            continue
    s = pywraplp.Solver.CreateSolver("GLOP")
    return s, "GLOP"


def _constraints(raw: list | None) -> list[HumanConstraint]:
    parsed: list[HumanConstraint] = []
    for item in raw or []:
        if isinstance(item, HumanConstraint):
            parsed.append(item)
        else:
            parsed.append(HumanConstraint.model_validate(item))
    return parsed


def solve_bundle(
    bundle: AgentBundle,
    risk_weight: float | None = None,
    enforce_low_risk: bool = True,
    human_constraints: list | None = None,
) -> SolverResult:
    """MILP: quantities are decision variables. LLM does not compute them."""
    from ortools.linear_solver import pywraplp

    risk_weight = settings.risk_penalty_weight if risk_weight is None else risk_weight
    constraints = _constraints(human_constraints)
    excluded_suppliers = {c.code for c in constraints if c.kind == "exclude_supplier" and c.code}
    excluded_routes = {c.code for c in constraints if c.kind == "exclude_route" and c.code}
    max_lead = min(
        (int(c.value) for c in constraints if c.kind == "max_lead_time_days" and c.value is not None),
        default=None,
    )
    min_reliability = max(
        (float(c.value) for c in constraints if c.kind == "min_reliability" and c.value is not None),
        default=None,
    )
    share_caps = [
        float(c.value) for c in constraints if c.kind == "max_supplier_share" and c.value is not None
    ]
    max_share = min(share_caps) if share_caps else None
    solver, backend = _solver()
    if solver is None:
        return SolverResult(
            status="solver_unavailable",
            total_cost=0,
            procurement_cost=0,
            transport_cost=0,
            risk_penalty_cost=0,
            delivery_time_hours=0,
            infeasibility="OR-Tools solver could not be created",
        )

    offers = {}
    for offer in bundle.suppliers.offers:
        if not offer.eligible:
            continue
        if offer.supplier_code in excluded_suppliers:
            continue
        if max_lead is not None and offer.lead_time_days > max_lead:
            continue
        if min_reliability is not None and offer.reliability_score < min_reliability:
            continue
        offers[offer.supplier_id] = offer
    lanes: list[tuple[SupplierOffer, RouteOption]] = []
    for route in bundle.routes.routes:
        offer = offers.get(route.supplier_id)
        if not offer:
            continue
        if route.code in excluded_routes:
            continue
        if route.capacity_units <= 0:
            continue
        lanes.append((offer, route))

    demand = bundle.inventory.net_requirement
    if demand <= 0:
        return SolverResult(
            status="OPTIMAL",
            total_cost=0,
            procurement_cost=0,
            transport_cost=0,
            risk_penalty_cost=0,
            delivery_time_hours=0,
            objective_notes=["Net requirement is 0; inventory covers demand plus safety stock."],
        )

    if not lanes:
        return SolverResult(
            status="INFEASIBLE",
            total_cost=0,
            procurement_cost=0,
            transport_cost=0,
            risk_penalty_cost=0,
            delivery_time_hours=0,
            unmet_demand=demand,
            infeasibility="No eligible supplier-route lanes",
        )

    integer = backend != "GLOP"
    x = {}
    for offer, route in lanes:
        name = f"x_{offer.supplier_code}_{route.code}"
        ub = min(offer.monthly_capacity, route.capacity_units, demand + offer.moq)
        if integer:
            x[(offer.supplier_id, route.route_id)] = solver.IntVar(0, ub, name)
        else:
            x[(offer.supplier_id, route.route_id)] = solver.NumVar(0, ub, name)

    # Supplier capacity + MOQ
    y = {}
    for sid, offer in offers.items():
        related = [var for (s, r), var in x.items() if s == sid]
        if not related:
            continue
        total = solver.Sum(related)
        solver.Add(total <= offer.monthly_capacity)
        if integer:
            y[sid] = solver.BoolVar(f"use_{offer.supplier_code}")
            solver.Add(total <= offer.monthly_capacity * y[sid])
            solver.Add(total >= offer.moq * y[sid])

    # Warehouse remaining capacity
    incoming = {}
    for (sid, rid), var in x.items():
        route = next(r for o, r in lanes if r.route_id == rid)
        incoming.setdefault(route.warehouse_id, [])
        incoming[route.warehouse_id].append(var)
    inv_by_wh = {row.warehouse_id: row for row in bundle.inventory.rows}
    for wh_id, vars_ in incoming.items():
        inv = inv_by_wh.get(wh_id)
        if not inv:
            continue
        remaining = max(0, inv.capacity_units - inv.on_hand)
        solver.Add(solver.Sum(vars_) <= remaining)

    solver.Add(solver.Sum(x.values()) >= demand)

    if enforce_low_risk and integer:
        total = solver.Sum(x.values())
        weighted_rel = solver.Sum(
            var * next(o.reliability_score for o, r in lanes if r.route_id == rid)
            for (sid, rid), var in x.items()
        )
        solver.Add(weighted_rel >= 0.90 * total)
        high_vars = [
            var
            for (sid, rid), var in x.items()
            if offers[sid].risk_tier == "high"
        ]
        if high_vars:
            solver.Add(solver.Sum(high_vars) <= 0.15 * total)
        for sid, offer in offers.items():
            related = [var for (s, r), var in x.items() if s == sid]
            if related:
                solver.Add(solver.Sum(related) <= 0.60 * total)

    if max_share is not None and integer and x:
        total_units = solver.Sum(x.values())
        for sid, offer in offers.items():
            related = [var for (s, _rid), var in x.items() if s == sid]
            if related:
                solver.Add(solver.Sum(related) <= max_share * total_units)

    obj_terms = []
    for (sid, rid), var in x.items():
        offer = offers[sid]
        route = next(r for o, r in lanes if r.route_id == rid)
        inv = inv_by_wh.get(route.warehouse_id)
        hold = (inv.holding_cost_per_unit if inv else 0.1) * 0.25
        penalty = risk_weight * (1 - offer.reliability_score) * offer.unit_price
        unit = offer.unit_price + route.effective_cost_per_unit + hold + penalty
        obj_terms.append(unit * var)

    solver.Minimize(solver.Sum(obj_terms))
    solver.SetTimeLimit(15_000)
    result = solver.Solve()

    status_map = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
        pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
        pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
        pywraplp.Solver.ABNORMAL: "ABNORMAL",
        pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
    }
    status = status_map.get(result, str(result))

    if status not in {"OPTIMAL", "FEASIBLE"}:
        # Relax low-risk concentration constraints and retry once.
        if enforce_low_risk:
            return solve_bundle(
                bundle,
                risk_weight=risk_weight,
                enforce_low_risk=False,
                human_constraints=human_constraints,
            )
        return SolverResult(
            status=status,
            total_cost=0,
            procurement_cost=0,
            transport_cost=0,
            risk_penalty_cost=0,
            delivery_time_hours=0,
            unmet_demand=demand,
            infeasibility="Solver could not find a feasible allocation",
            objective_notes=[f"backend={backend}"],
        )

    allocations: list[Allocation] = []
    proc = trans = pen = 0.0
    max_hours = 0.0
    for (sid, rid), var in x.items():
        qty = int(round(var.solution_value()))
        if qty <= 0:
            continue
        offer = offers[sid]
        route = next(r for o, r in lanes if r.route_id == rid)
        line_proc = qty * offer.unit_price
        line_tr = qty * route.effective_cost_per_unit
        line_pen = qty * risk_weight * (1 - offer.reliability_score) * offer.unit_price
        proc += line_proc
        trans += line_tr
        pen += line_pen
        hours = offer.lead_time_days * 24 + route.transit_hours
        max_hours = max(max_hours, hours)
        allocations.append(
            Allocation(
                supplier_code=offer.supplier_code,
                supplier_name=offer.supplier_name,
                warehouse_code=route.warehouse_code,
                route_code=route.code,
                mode=route.mode,
                quantity=qty,
                unit_price=offer.unit_price,
                transport_cost_per_unit=route.effective_cost_per_unit,
                line_cost=round(line_proc + line_tr, 2),
                lead_time_days=offer.lead_time_days,
                transit_hours=route.transit_hours,
                reliability_score=offer.reliability_score,
            )
        )

    filled = sum(a.quantity for a in allocations)
    return SolverResult(
        status=status,
        total_cost=round(proc + trans, 2),
        procurement_cost=round(proc, 2),
        transport_cost=round(trans, 2),
        risk_penalty_cost=round(pen, 2),
        delivery_time_hours=round(max_hours, 1),
        allocations=sorted(allocations, key=lambda a: (-a.quantity, a.supplier_code)),
        unmet_demand=max(0, demand - filled),
        objective_notes=[
            f"OR-Tools backend={backend}",
            "Objective minimizes procurement + transport + holding + reliability penalty.",
            "Quantities are solver outputs, not LLM estimates.",
            f"Low-risk constraints enforced={enforce_low_risk}",
            f"Human constraints applied={len(constraints)}",
        ],
    )

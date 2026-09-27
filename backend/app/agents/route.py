from __future__ import annotations

from app.agents.schemas import RouteOption, RouteResult, SupplierResult
from app.db.repositories import open_risk_events, routes_for_suppliers
from sqlalchemy.orm import Session


def run_route_agent(
    db: Session,
    suppliers: SupplierResult,
    disrupted_route_codes: set[str] | None = None,
    fuel_multiplier: float = 1.0,
) -> RouteResult:
    disrupted_route_codes = disrupted_route_codes or set()
    supplier_ids = [o.supplier_id for o in suppliers.offers if o.eligible]
    events = open_risk_events(db)
    event_route_ids = {e.affected_route_id for e in events if e.affected_route_id}
    options: list[RouteOption] = []
    for route in routes_for_suppliers(db, supplier_ids):
        disrupted = (
            route.status != "open"
            or route.code in disrupted_route_codes
            or route.id in event_route_ids
        )
        # congestion events still allow flow but we flag them; only explicit
        # disruption / non-open status zeros the lane in the solver.
        hard_block = route.status != "open" or route.code in disrupted_route_codes
        effective = round(route.cost_per_unit * route.fuel_factor * fuel_multiplier, 4)
        options.append(
            RouteOption(
                route_id=route.id,
                code=route.code,
                supplier_id=route.supplier_id,
                warehouse_id=route.warehouse_id,
                warehouse_code=route.warehouse.code,
                mode=route.mode,
                distance_km=route.distance_km,
                transit_hours=route.transit_hours,
                cost_per_unit=route.cost_per_unit,
                capacity_units=0 if hard_block else route.capacity_units,
                fuel_factor=route.fuel_factor,
                status="disrupted" if hard_block else route.status,
                disrupted=disrupted,
                effective_cost_per_unit=effective,
            )
        )
    notes = [
        "Route costs and capacities come from the routes table.",
        "Fuel multiplier scales transport cost only.",
    ]
    return RouteResult(routes=options, notes=notes)

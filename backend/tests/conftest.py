from __future__ import annotations

from app.agents.schemas import (
    AgentBundle,
    DemandResult,
    InventoryResult,
    InventoryRow,
    RiskResult,
    RouteOption,
    RouteResult,
    SupplierOffer,
    SupplierResult,
)
from scripts.seed import INVENTORY_A, ROUTES, SUPPLIER_PRODUCTS, SUPPLIERS, WAREHOUSES


def product_a_bundle(
    demand_to_meet: int = 10000,
    failed: set[str] | None = None,
    price_mult: float = 1.0,
    fuel_mult: float = 1.0,
    inv_factor: float = 1.0,
    disrupted: set[str] | None = None,
) -> AgentBundle:
    failed = failed or set()
    disrupted = disrupted or set()
    suppliers = {s["code"]: s for s in SUPPLIERS}
    offers: list[SupplierOffer] = []
    sid = 1
    sid_map: dict[str, int] = {}
    for code, s in suppliers.items():
        sid_map[code] = sid
        sid += 1
    wid = 1
    wid_map: dict[str, int] = {}
    for w in WAREHOUSES:
        wid_map[w["code"]] = wid
        wid += 1

    for s, p, price, cap, lead, moq in SUPPLIER_PRODUCTS:
        if p != "PROD-A":
            continue
        sup = suppliers[s]
        eligible = s not in failed and lead <= 31
        offers.append(
            SupplierOffer(
                supplier_id=sid_map[s],
                supplier_code=s,
                supplier_name=sup["name"],
                unit_price=round(price * price_mult, 4),
                monthly_capacity=cap,
                lead_time_days=lead,
                moq=moq,
                reliability_score=sup["reliability_score"],
                risk_tier=sup["risk_tier"],
                status="active",
                eligible=eligible,
                reasons=["failed"] if s in failed else [],
            )
        )

    routes: list[RouteOption] = []
    rid = 1
    for c, s, w, mode, km, hrs, cost, cap, fuel, status in ROUTES:
        hard = c in disrupted or status != "open"
        routes.append(
            RouteOption(
                route_id=rid,
                code=c,
                supplier_id=sid_map[s],
                warehouse_id=wid_map[w],
                warehouse_code=w,
                mode=mode,
                distance_km=km,
                transit_hours=hrs,
                cost_per_unit=cost,
                capacity_units=0 if hard else cap,
                fuel_factor=fuel,
                status="disrupted" if hard else status,
                disrupted=hard,
                effective_cost_per_unit=round(cost * fuel * fuel_mult, 4),
            )
        )
        rid += 1

    inv_rows: list[InventoryRow] = []
    for w in WAREHOUSES:
        on_hand, reserved, rop, ss, hold = INVENTORY_A[w["code"]]
        on_hand = int(round(on_hand * inv_factor))
        available = max(0, on_hand - reserved)
        inv_rows.append(
            InventoryRow(
                warehouse_id=wid_map[w["code"]],
                warehouse_code=w["code"],
                on_hand=on_hand,
                reserved=reserved,
                available=available,
                reorder_point=rop,
                safety_stock=ss,
                holding_cost_per_unit=hold,
                capacity_units=w["capacity_units"],
            )
        )
    total_available = sum(r.available for r in inv_rows)
    total_ss = sum(r.safety_stock for r in inv_rows)
    safety_gap = max(0, total_ss - total_available)
    net = max(0, demand_to_meet - total_available + safety_gap)

    return AgentBundle(
        demand=DemandResult(
            product_id=1,
            product_sku="PROD-A",
            product_name="Product A",
            requested_quantity=demand_to_meet,
            forecast_units=9200,
            forecast_method="seasonal_naive_blend_3ma",
            history_months=24,
            history=[],
            demand_to_meet=demand_to_meet,
        ),
        suppliers=SupplierResult(offers=offers),
        routes=RouteResult(routes=routes),
        inventory=InventoryResult(
            rows=inv_rows,
            total_available=total_available,
            total_safety_stock=total_ss,
            net_requirement=net,
        ),
        risk=RiskResult(score=42.0, drivers=[]),
    )

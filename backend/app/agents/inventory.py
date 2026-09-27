from __future__ import annotations

from app.agents.schemas import DemandResult, InventoryResult, InventoryRow
from app.core.provenance import Provenanced
from app.db.repositories import inventory_for_product
from sqlalchemy.orm import Session


def run_inventory_agent(
    db: Session,
    demand: DemandResult,
    inventory_factor: float = 1.0,
) -> InventoryResult:
    rows: list[InventoryRow] = []
    for inv in inventory_for_product(db, demand.product_id):
        on_hand = int(round(inv.on_hand * inventory_factor))
        available = max(0, on_hand - inv.reserved)
        rows.append(
            InventoryRow(
                warehouse_id=inv.warehouse_id,
                warehouse_code=inv.warehouse.code,
                on_hand=on_hand,
                reserved=inv.reserved,
                available=available,
                reorder_point=inv.reorder_point,
                safety_stock=inv.safety_stock,
                holding_cost_per_unit=inv.holding_cost_per_unit,
                capacity_units=inv.warehouse.capacity_units,
            )
        )
    total_available = sum(r.available for r in rows)
    total_ss = sum(r.safety_stock for r in rows)
    # Keep a safety-stock buffer after fulfilling demand.
    safety_gap = max(0, total_ss - total_available)
    net = max(0, demand.demand_to_meet - total_available + safety_gap)
    notes = [
        "Available = on_hand - reserved from the inventory table.",
        "Net requirement includes a safety-stock gap so DCs are not stripped bare.",
    ]
    if inventory_factor != 1.0:
        notes.append(f"What-if inventory factor applied: {inventory_factor}")
    return InventoryResult(
        rows=rows,
        total_available=total_available,
        total_safety_stock=total_ss,
        net_requirement=net,
        notes=notes,
        provenance={
            "total_available": Provenanced(value=total_available, source="database"),
            "net_requirement": Provenanced(
                value=net, source="agent_reasoning", note="forecast/user demand minus available plus safety gap"
            ),
        },
    )

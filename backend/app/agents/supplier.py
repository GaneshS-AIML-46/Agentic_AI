from __future__ import annotations

from app.agents.schemas import DemandResult, SupplierOffer, SupplierResult
from app.db.repositories import supplier_offers
from app.llm.factory import Intent
from sqlalchemy.orm import Session


def run_supplier_agent(
    db: Session,
    intent: Intent,
    demand: DemandResult,
    failed_supplier_codes: set[str] | None = None,
    price_multiplier: float = 1.0,
) -> SupplierResult:
    failed_supplier_codes = failed_supplier_codes or set()
    offers: list[SupplierOffer] = []
    rows = supplier_offers(db, demand.product_id)
    for sp in rows:
        supplier = sp.supplier
        eligible = True
        reasons: list[str] = []
        if supplier.status != "active":
            eligible = False
            reasons.append("supplier inactive")
        if supplier.code in failed_supplier_codes:
            eligible = False
            reasons.append("supplier failure scenario")
        if sp.lead_time_days > intent.lead_time_days_max:
            eligible = False
            reasons.append(
                f"lead time {sp.lead_time_days}d exceeds horizon {intent.lead_time_days_max}d"
            )
        if intent.low_risk and supplier.risk_tier == "high":
            reasons.append("high risk tier — allowed but penalized for low-risk objective")
        unit_price = round(sp.unit_price * price_multiplier, 4)
        offers.append(
            SupplierOffer(
                supplier_id=supplier.id,
                supplier_code=supplier.code,
                supplier_name=supplier.name,
                unit_price=unit_price,
                monthly_capacity=sp.monthly_capacity,
                lead_time_days=sp.lead_time_days,
                moq=sp.moq,
                reliability_score=supplier.reliability_score,
                risk_tier=supplier.risk_tier,
                status=supplier.status,
                eligible=eligible,
                reasons=reasons,
            )
        )
    notes = [
        "Prices, capacity, MOQ and lead times come from supplier_products (database).",
        "The agent only marks eligibility; it does not allocate quantities.",
    ]
    if price_multiplier != 1.0:
        notes.append(f"What-if price multiplier applied: {price_multiplier}")
    return SupplierResult(offers=offers, notes=notes)

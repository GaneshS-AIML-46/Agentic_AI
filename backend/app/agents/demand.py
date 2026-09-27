from __future__ import annotations

from app.agents.schemas import DemandResult
from app.core.provenance import Provenanced
from app.db.repositories import monthly_order_history, resolve_product
from app.llm.factory import Intent
from sqlalchemy.orm import Session


def _seasonal_forecast(history: list[dict]) -> tuple[int, str]:
    if not history:
        return 0, "no_history"
    quantities = [h["quantity"] for h in history]
    if len(quantities) >= 12:
        last12 = quantities[-12:]
        prev = quantities[-24:-12] if len(quantities) >= 24 else last12
        # seasonal naive blended with trailing 3-month mean
        seasonal = prev[-1] if prev else last12[-1]
        recent = sum(last12[-3:]) / 3
        forecast = 0.55 * seasonal + 0.45 * recent
        return int(round(forecast)), "seasonal_naive_blend_3ma"
    window = quantities[-3:] if len(quantities) >= 3 else quantities
    return int(round(sum(window) / len(window))), "trailing_mean"


def run_demand_agent(db: Session, intent: Intent) -> DemandResult:
    product = resolve_product(db, intent.product_query)
    if product is None:
        raise ValueError(f"Unknown product: {intent.product_query}")
    history = monthly_order_history(db, product.id, months=24)
    forecast, method = _seasonal_forecast(history)
    requested = intent.quantity
    demand_to_meet = requested if requested is not None else forecast
    notes = [
        "Forecast is computed from synthetic historical orders, not by the LLM.",
        "If the user specified a quantity, that quantity is the demand to meet.",
    ]
    return DemandResult(
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        requested_quantity=requested,
        forecast_units=forecast,
        forecast_method=method,
        history_months=len(history),
        history=history[-12:],
        demand_to_meet=demand_to_meet,
        notes=notes,
        provenance={
            "forecast_units": Provenanced(
                value=forecast, source="forecast_model", note=method
            ),
            "demand_to_meet": Provenanced(
                value=demand_to_meet,
                source="user_query" if requested is not None else "forecast_model",
            ),
        },
    )

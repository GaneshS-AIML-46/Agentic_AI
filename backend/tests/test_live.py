from app.live.feed import advance
from app.llm.factory import fallback_narrative
from app.optimization.solver import solve_bundle
from tests.conftest import product_a_bundle


def test_higher_unit_price_raises_total_cost():
    baseline = solve_bundle(product_a_bundle(10000, price_mult=1.0), enforce_low_risk=False)
    dearer = solve_bundle(product_a_bundle(10000, price_mult=1.01), enforce_low_risk=False)
    assert baseline.status in {"OPTIMAL", "FEASIBLE"}
    assert dearer.total_cost > baseline.total_cost


def test_second_tick_same_minute_does_not_double_stock_move():
    fuel, stock, applied, moved = advance(612.0, 1000, "2026-10-05T18:15", None)
    assert moved is True
    assert stock != 1000
    again_fuel, again_stock, again_applied, again_moved = advance(fuel, stock, "2026-10-05T18:15", applied)
    assert again_moved is False
    assert again_stock == stock
    assert again_fuel == fuel
    assert again_applied == applied


def test_provider_order_splits_work():
    from app.llm.factory import provider_order

    have = {"groq", "openai", "gemini"}
    assert provider_order("intent", have)[0] == "groq"
    assert provider_order("narrative", have)[0] == "openai"
    assert provider_order("narrative", {"gemini"}) == ["gemini"]


def test_narrative_changes_with_each_request():
    facts = {"product_name": "Product A", "demand_to_meet": 1000, "forecast_units": 900, "net_requirement": 400, "status": "OPTIMAL", "total_cost": 10, "procurement_cost": 8, "transport_cost": 2, "delivery_time_hours": 40, "risk_score": 12}
    evidence = [{"title": "Sourcing Policy", "snippet": "Prefer reliable suppliers."}]
    first = fallback_narrative("I need Product A with low risk", facts, evidence, ["parsed intent"])
    second = fallback_narrative("Procure Product C as cheaply as possible", facts, evidence, ["parsed intent"])
    assert first["reason"] != second["reason"]
    assert first["evidence"][0]["relevance"] != second["evidence"][0]["relevance"]
    assert first["trace"] != second["trace"]
    assert "or-tools" in first["reason"].lower()

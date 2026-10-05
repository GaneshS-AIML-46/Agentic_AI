from app.core.config import Settings
from app.hitl.constraints import parse_human_text
from app.llm.factory import parse_intent
from app.optimization.solver import solve_bundle
from app.rag.embed import mock_embed
from app.scenarios.engine import scenario_from_text
from app.whatif.engine import WhatIfRequest, build_patch, delivery_hours
from tests.conftest import product_a_bundle


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def test_default_gemini_model_is_current():
    assert Settings.model_fields["gemini_model"].default == "gemini-3.8-flash"


def test_mock_embeddings_rank_related_text_higher():
    policy = mock_embed("safety stock policy for warehouses")
    related = mock_embed("safety stock policy for distribution centers")
    unrelated = mock_embed("marine fuel surcharge ocean freight index")
    assert _cosine(policy, related) > _cosine(policy, unrelated)


def test_mock_embeddings_are_deterministic():
    assert mock_embed("Product A sourcing policy") == mock_embed("Product A sourcing policy")


def test_feedback_becomes_constraints():
    parsed = parse_human_text("exclude supplier SUP-C and max lead time 20 days")
    by_kind = {item.kind: item for item in parsed}
    assert by_kind["exclude_supplier"].code == "SUP-C"
    assert by_kind["max_lead_time_days"].value == 20


def test_intent_extracts_supplier_failure():
    intent = parse_intent("I need 5000 units of Product A if supplier SUP-C fails")
    assert intent.quantity == 5000
    assert "SUP-C" in intent.failed_supplier_codes


def test_natural_language_scenario_patch():
    scenario = scenario_from_text("supplier SUP-C fails and fuel +15%")
    assert "SUP-C" in scenario.patch.failed_supplier_codes
    assert scenario.patch.fuel_multiplier == 1.15
    built = build_patch(WhatIfRequest(scenario="natural_language", text="demand +20%"))
    assert built.demand_multiplier == 1.2


def test_solver_applies_human_exclude():
    result = solve_bundle(
        product_a_bundle(10000),
        human_constraints=[{"kind": "exclude_supplier", "code": "SUP-C", "raw": "exclude SUP-C"}],
    )
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert all(row.supplier_code != "SUP-C" for row in result.allocations)


def test_delivery_hours_falls_back_to_allocations():
    hours = delivery_hours(
        {"delivery_time_hours": 0},
        {"allocations": [{"lead_time_days": 2, "transit_hours": 10, "quantity": 100}]},
    )
    assert hours == 58.0

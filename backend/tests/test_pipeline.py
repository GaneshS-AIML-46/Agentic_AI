from app.llm.factory import parse_intent
from app.optimization.solver import solve_bundle
from app.rag.ingest import chunk_text
from app.validation.validator import validate_plan
from app.whatif.engine import WhatIfRequest, build_patch
from scripts.seed import PRODUCTS, ROUTES, SUPPLIERS, generate_order_rows
from tests.conftest import product_a_bundle


def test_synthetic_catalog_sizes():
    assert len(PRODUCTS) == 10
    assert any(p["name"] == "Product A" for p in PRODUCTS)
    assert len(SUPPLIERS) == 7
    assert len(ROUTES) == 16


def test_order_history_is_seasonal():
    rows = generate_order_rows(24)
    assert len(rows) == 24 * 10 * 4
    pa = [r for r in rows if r["product_sku"] == "PROD-A"]
    assert sum(r["quantity"] for r in pa) > 100_000


def test_intent_example_query():
    intent = parse_intent(
        "I need 10,000 units of Product A next month. Find the lowest-cost supply plan with low risk."
    )
    assert intent.product_query == "Product A"
    assert intent.quantity == 10000
    assert intent.low_risk is True


def test_chunk_text():
    chunks = chunk_text("alpha " * 200, size=80, overlap=10)
    assert len(chunks) > 2


def test_solver_meets_product_a_demand():
    bundle = product_a_bundle(10000)
    result = solve_bundle(bundle, enforce_low_risk=True)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    filled = sum(a.quantity for a in result.allocations)
    assert filled >= bundle.inventory.net_requirement - 1
    assert result.total_cost > 0
    report = validate_plan(bundle, result)
    assert report["ok"] is True


def test_solver_does_not_invent_over_capacity():
    bundle = product_a_bundle(10000)
    result = solve_bundle(bundle)
    by = {}
    cap = {o.supplier_code: o.monthly_capacity for o in bundle.suppliers.offers}
    for a in result.allocations:
        by[a.supplier_code] = by.get(a.supplier_code, 0) + a.quantity
    for code, qty in by.items():
        assert qty <= cap[code]


def test_whatif_supplier_failure_excludes_supplier():
    baseline = solve_bundle(product_a_bundle(10000))
    failed = solve_bundle(product_a_bundle(10000, failed={"SUP-C"}))
    assert all(a.supplier_code != "SUP-C" for a in failed.allocations)
    assert failed.status in {"OPTIMAL", "FEASIBLE"}
    assert failed.total_cost >= baseline.total_cost - 1e-6


def test_whatif_patch_builder():
    p = build_patch(WhatIfRequest(scenario="demand_increase", pct=25))
    assert p.demand_multiplier == 1.25
    p2 = build_patch(WhatIfRequest(scenario="supplier_failure", supplier_code="SUP-A"))
    assert "SUP-A" in p2.failed_supplier_codes

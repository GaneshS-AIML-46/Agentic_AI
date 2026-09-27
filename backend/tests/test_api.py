import os

import pytest

pytest.importorskip("fastapi")


@pytest.fixture(scope="session")
def client():
    if os.getenv("SKIP_API_TESTS") == "1":
        pytest.skip("API tests skipped")
    try:
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as c:
            health = c.get("/api/v1/health")
            if health.status_code != 200 or health.json().get("database") is False:
                pytest.skip("Postgres not available")
            yield c
    except Exception as exc:
        pytest.skip(f"API unavailable: {exc}")


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["synthetic_data"] is True


def test_catalog_has_product_a(client):
    res = client.get("/api/v1/catalog")
    names = [p["name"] for p in res.json()["products"]]
    assert "Product A" in names


def test_decision_example(client):
    res = client.post(
        "/api/v1/decisions",
        json={
            "query": "I need 10,000 units of Product A next month. Find the lowest-cost supply plan with low risk."
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["optimization_status"] in {"OPTIMAL", "FEASIBLE"}
    assert body["total_cost"] > 0
    assert body["supplier_allocation"]
    assert body["retrieved_evidence"]
    reason = body["explainable_recommendation"]["reason"]
    assert "solver" in reason.lower() or "OR-Tools" in reason


def test_whatif_supplier_failure_api(client):
    base = client.post(
        "/api/v1/decisions",
        json={"query": "I need 10,000 units of Product A next month. Find the lowest-cost supply plan with low risk."},
    ).json()
    scenario = client.post(
        "/api/v1/what-if",
        json={"run_id": base["run_id"], "scenario": "supplier_failure", "supplier_code": "SUP-C"},
    ).json()
    assert scenario["what_if"]["comparison"]
    codes = [a["supplier_code"] for a in scenario["supplier_allocation"]]
    assert "SUP-C" not in codes

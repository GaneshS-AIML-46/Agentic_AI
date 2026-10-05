from app.llm import factory


def _generated_json(provider: str, system: str, user: str):
    if provider == "gemini":
        raise RuntimeError("Gemini temporarily unavailable")
    return {
        "product_query": "Product C",
        "quantity": 100,
        "horizon": "next_month",
        "lead_time_days_max": 31,
        "objective": "min_cost_low_risk",
        "low_risk": True,
        "notes": "Parsed by backup provider.",
        "summary": "The model selected the solver-backed plan.",
        "reason": "The solver selected this plan from the available supply facts.",
        "kpi_note": "The solver calculated the cost.",
        "allocation_note": "The allocation follows solver output.",
        "routes_note": "The routes follow solver output.",
        "inventory_note": "Inventory was included in the plan.",
        "evidence": [],
        "trace": ["Backup model parsed the request", "Backup model summarized the plan"],
    }


def test_intent_uses_backup_provider_when_gemini_fails(monkeypatch):
    monkeypatch.setattr(factory.settings, "llm_provider", "gemini")
    monkeypatch.setattr(factory, "available_providers", lambda: ["gemini", "openai"])
    monkeypatch.setattr(factory, "complete_json", _generated_json)

    intent = factory.parse_intent("I need 100 units of Product C next month.")

    assert intent.llm_provider == "openai"
    assert intent.product_query == "Product C"
    assert intent.quantity == 100
    assert intent.llm_warning is None


def test_narrative_and_trace_use_backup_provider_when_gemini_fails(monkeypatch):
    monkeypatch.setattr(factory.settings, "llm_provider", "gemini")
    monkeypatch.setattr(factory.settings, "openai_model", "test-backup-model")
    monkeypatch.setattr(factory, "available_providers", lambda: ["gemini", "openai"])
    monkeypatch.setattr(factory, "complete_json", _generated_json)

    result = factory.narrate_plan(
        "I need 100 units of Product C.",
        {"product_name": "Product C", "demand_to_meet": 100},
        [],
        ["solver completed"],
    )

    assert result["writer"] == "openai (test-backup-model)"
    assert result["reason"].startswith("The solver selected")
    assert result["trace"] == [
        "Backup model parsed the request",
        "Backup model summarized the plan",
    ]

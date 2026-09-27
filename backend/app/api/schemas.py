from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.whatif.engine import WhatIfRequest


class DecisionRequest(BaseModel):
    query: str = Field(
        examples=[
            "I need 10,000 units of Product A next month. Find the lowest-cost supply plan with low risk."
        ]
    )


class WhatIfBody(WhatIfRequest):
    run_id: int | None = None
    query: str | None = None


class DecisionResponse(BaseModel):
    run_id: int
    query: str
    demand_forecast: dict[str, Any]
    supplier_allocation: list[dict[str, Any]]
    routes: list[dict[str, Any]]
    inventory_plan: dict[str, Any]
    total_cost: float | None
    delivery_time_hours: float | None
    risk_score: float | None
    optimization_status: str | None
    retrieved_evidence: list[dict[str, Any]]
    explainable_recommendation: dict[str, Any]
    agent_trace: list[str]
    validation: dict[str, Any]
    what_if: dict[str, Any] | None = None
    data_disclaimer: str

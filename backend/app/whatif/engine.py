from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ScenarioType = Literal[
    "demand_increase",
    "supplier_failure",
    "price_increase",
    "fuel_increase",
    "route_disruption",
    "inventory_shortage",
]


class WhatIfRequest(BaseModel):
    scenario: ScenarioType
    pct: float | None = Field(default=None, description="Percentage, e.g. 20 for +20%")
    supplier_code: str | None = None
    route_code: str | None = None


class WhatIfPatch(BaseModel):
    demand_multiplier: float = 1.0
    price_multiplier: float = 1.0
    fuel_multiplier: float = 1.0
    inventory_factor: float = 1.0
    failed_supplier_codes: list[str] = Field(default_factory=list)
    disrupted_route_codes: list[str] = Field(default_factory=list)
    label: str = ""


def build_patch(req: WhatIfRequest) -> WhatIfPatch:
    pct = (req.pct or 0) / 100.0
    if req.scenario == "demand_increase":
        return WhatIfPatch(
            demand_multiplier=1 + (pct or 0.2),
            label=f"Demand +{(req.pct or 20)}%",
        )
    if req.scenario == "supplier_failure":
        code = req.supplier_code or "SUP-C"
        return WhatIfPatch(failed_supplier_codes=[code], label=f"Supplier failure {code}")
    if req.scenario == "price_increase":
        return WhatIfPatch(
            price_multiplier=1 + (pct or 0.1),
            label=f"Price +{(req.pct or 10)}%",
        )
    if req.scenario == "fuel_increase":
        return WhatIfPatch(
            fuel_multiplier=1 + (pct or 0.15),
            label=f"Fuel +{(req.pct or 15)}%",
        )
    if req.scenario == "route_disruption":
        code = req.route_code or "RT-C-ROT-OC"
        return WhatIfPatch(disrupted_route_codes=[code], label=f"Route disrupted {code}")
    if req.scenario == "inventory_shortage":
        return WhatIfPatch(
            inventory_factor=max(0.0, 1 - (pct or 0.5)),
            label=f"Inventory {(req.pct or 50)}% short",
        )
    return WhatIfPatch(label="noop")


def diff_results(baseline: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    def _num(path, default=0.0):
        cur = baseline
        for p in path:
            cur = (cur or {}).get(p, default) if isinstance(cur, dict) else default
        b = cur if isinstance(cur, (int, float)) else default
        cur = scenario
        for p in path:
            cur = (cur or {}).get(p, default) if isinstance(cur, dict) else default
        s = cur if isinstance(cur, (int, float)) else default
        return {"baseline": b, "scenario": s, "delta": round(s - b, 2)}

    return {
        "total_cost": _num(["total_cost"]),
        "delivery_time_hours": _num(["delivery_time_hours"]),
        "risk_score": _num(["risk_score"]),
        "unmet_demand": _num(["unmet_demand"]),
    }

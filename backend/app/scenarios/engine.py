from __future__ import annotations

from pydantic import BaseModel, Field

from app.hitl.constraints import HumanConstraint, parse_human_text
from app.whatif.engine import WhatIfPatch


class ScenarioState(BaseModel):
    """Baseline request plus the fact patch and human constraints for this run."""

    label: str = "baseline"
    patch: WhatIfPatch = Field(default_factory=WhatIfPatch)
    constraints: list[HumanConstraint] = Field(default_factory=list)
    narrative: str = ""


def constraints_to_patch(constraints: list[HumanConstraint], label: str = "") -> WhatIfPatch:
    failed: list[str] = []
    routes: list[str] = []
    demand = price = fuel = inventory = 1.0
    for item in constraints:
        if item.kind == "exclude_supplier" and item.code:
            failed.append(item.code)
        elif item.kind == "exclude_route" and item.code:
            routes.append(item.code)
        elif item.kind == "demand_multiplier" and item.value is not None:
            demand = item.value
        elif item.kind == "price_multiplier" and item.value is not None:
            price = item.value
        elif item.kind == "fuel_multiplier" and item.value is not None:
            fuel = item.value
        elif item.kind == "inventory_factor" and item.value is not None:
            inventory = item.value
    text = label or ", ".join(c.raw for c in constraints if c.raw) or "scenario"
    return WhatIfPatch(
        demand_multiplier=demand,
        price_multiplier=price,
        fuel_multiplier=fuel,
        inventory_factor=inventory,
        failed_supplier_codes=list(dict.fromkeys(failed)),
        disrupted_route_codes=list(dict.fromkeys(routes)),
        label=text,
    )


def combine_patches(explicit: WhatIfPatch | None, inferred: WhatIfPatch) -> WhatIfPatch:
    """Keep an API patch when it changes a factor; otherwise use the inferred one."""
    if explicit is None:
        return inferred

    def pick(explicit_value: float, inferred_value: float) -> float:
        return inferred_value if explicit_value == 1.0 else explicit_value

    failed = list(dict.fromkeys(explicit.failed_supplier_codes + inferred.failed_supplier_codes))
    routes = list(dict.fromkeys(explicit.disrupted_route_codes + inferred.disrupted_route_codes))
    label = explicit.label or inferred.label
    return WhatIfPatch(
        demand_multiplier=pick(explicit.demand_multiplier, inferred.demand_multiplier),
        price_multiplier=pick(explicit.price_multiplier, inferred.price_multiplier),
        fuel_multiplier=pick(explicit.fuel_multiplier, inferred.fuel_multiplier),
        inventory_factor=pick(explicit.inventory_factor, inferred.inventory_factor),
        failed_supplier_codes=failed,
        disrupted_route_codes=routes,
        label=label,
    )


def scenario_from_text(text: str, label: str = "") -> ScenarioState:
    constraints = parse_human_text(text)
    patch = constraints_to_patch(constraints, label=label or text.strip()[:120])
    narrative = patch.label if constraints else "No scenario changes detected."
    return ScenarioState(label=patch.label, patch=patch, constraints=constraints, narrative=narrative)


def merge_constraints(*groups: list[HumanConstraint]) -> list[HumanConstraint]:
    merged: list[HumanConstraint] = []
    seen: set[tuple] = set()
    for group in groups:
        for item in group:
            key = (item.kind, item.code, item.value)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged

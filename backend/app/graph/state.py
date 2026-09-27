from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    query: str
    intent: dict[str, Any]
    agents_needed: list[str]
    evidence: list[dict[str, Any]]
    demand: dict[str, Any]
    suppliers: dict[str, Any]
    routes: dict[str, Any]
    inventory: dict[str, Any]
    risk: dict[str, Any]
    solver: dict[str, Any]
    validation: dict[str, Any]
    recommendation: dict[str, Any]
    patch: dict[str, Any]
    replan_count: int
    trace: list[str]

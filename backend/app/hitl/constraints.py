from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

ConstraintKind = Literal[
    "exclude_supplier",
    "exclude_route",
    "max_lead_time_days",
    "min_reliability",
    "max_supplier_share",
    "demand_multiplier",
    "price_multiplier",
    "fuel_multiplier",
    "inventory_factor",
]

_SUPPLIER = r"(SUP-[A-Z0-9]+)"
_ROUTE = r"(RT-[A-Z0-9]+(?:-[A-Z0-9]+)+)"


class HumanConstraint(BaseModel):
    kind: ConstraintKind
    code: str | None = None
    value: float | None = None
    raw: str = ""


def _pct_multiplier(pct: float, direction: str = "up") -> float:
    factor = abs(pct) / 100.0
    if direction == "down":
        return max(0.0, 1.0 - factor)
    return 1.0 + factor


def parse_human_text(text: str) -> list[HumanConstraint]:
    """Turn planner language into solver and scenario constraints."""
    if not text or not text.strip():
        return []
    found: list[HumanConstraint] = []
    seen: set[tuple] = set()

    def add(kind: ConstraintKind, raw: str, code: str | None = None, value: float | None = None) -> None:
        key = (kind, (code or "").upper(), value)
        if key in seen:
            return
        seen.add(key)
        found.append(HumanConstraint(kind=kind, code=code.upper() if code else None, value=value, raw=raw.strip()))

    for match in re.finditer(
        rf"(?:exclude|avoid|without|drop|remove|don'?t use|do not use)\s+(?:supplier\s+)?{_SUPPLIER}",
        text,
        re.I,
    ):
        add("exclude_supplier", match.group(0), match.group(1))

    for match in re.finditer(
        rf"(?:supplier\s+)?{_SUPPLIER}\s+(?:fails?|failure|is down|goes down|outage|unavailable)",
        text,
        re.I,
    ):
        add("exclude_supplier", match.group(0), match.group(1))

    for match in re.finditer(
        rf"(?:disrupt|close|block|shut)\s+(?:route\s+)?{_ROUTE}",
        text,
        re.I,
    ):
        add("exclude_route", match.group(0), match.group(1))

    for match in re.finditer(
        r"(?:max(?:imum)?|within|under|less than)\s+lead\s*time(?:\s+of)?\s+(\d+)\s*days?",
        text,
        re.I,
    ):
        add("max_lead_time_days", match.group(0), value=float(match.group(1)))

    for match in re.finditer(
        r"(?:min(?:imum)?\s+)?reliability\s+(?:of\s+|above\s+|at least\s+)?(\d+(?:\.\d+)?)\s*%?",
        text,
        re.I,
    ):
        raw_val = float(match.group(1))
        value = raw_val / 100.0 if raw_val > 1 else raw_val
        add("min_reliability", match.group(0), value=value)

    for match in re.finditer(
        r"(?:cap|limit)\s+(?:any\s+)?supplier(?:\s+share)?\s+(?:at|to)?\s*(\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    ):
        add("max_supplier_share", match.group(0), value=float(match.group(1)) / 100.0)

    for match in re.finditer(
        r"demand\s+(?:increas(?:e|es)|up|spike|\+)\s*(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    ):
        add("demand_multiplier", match.group(0), value=_pct_multiplier(float(match.group(1))))

    for match in re.finditer(
        r"(\d+(?:\.\d+)?)\s*%\s+(?:more|higher)\s+demand",
        text,
        re.I,
    ):
        add("demand_multiplier", match.group(0), value=_pct_multiplier(float(match.group(1))))

    for match in re.finditer(
        r"(?:price|prices)\s+(?:increas(?:e|es)|up|\+)\s*(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    ):
        add("price_multiplier", match.group(0), value=_pct_multiplier(float(match.group(1))))

    for match in re.finditer(
        r"fuel\s+(?:increas(?:e|es)|up|\+)\s*(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    ):
        add("fuel_multiplier", match.group(0), value=_pct_multiplier(float(match.group(1))))

    for match in re.finditer(
        r"inventory\s+(?:short(?:age)?|down|drop)\s*(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    ):
        add("inventory_factor", match.group(0), value=_pct_multiplier(float(match.group(1)), "down"))

    return found

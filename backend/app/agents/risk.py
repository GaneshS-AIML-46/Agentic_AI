from __future__ import annotations

from app.agents.schemas import RiskDriver, RiskResult, RouteResult, SupplierResult
from app.db.repositories import latest_market_prices, open_risk_events, weather_events
from sqlalchemy.orm import Session


_SEV = {"high": 80.0, "medium": 45.0, "low": 15.0}


def run_risk_agent(
    db: Session,
    suppliers: SupplierResult,
    routes: RouteResult,
    scenario_label: str = "",
) -> RiskResult:
    drivers: list[RiskDriver] = []
    eligible = [o for o in suppliers.offers if o.eligible]
    if eligible:
        avg_rel = sum(o.reliability_score for o in eligible) / len(eligible)
        rel_score = (1 - avg_rel) * 100
        drivers.append(
            RiskDriver(
                kind="supplier_reliability",
                detail=f"Mean reliability of eligible suppliers is {avg_rel:.2f}.",
                severity="medium" if rel_score > 10 else "low",
                score_contribution=round(rel_score * 0.4, 2),
            )
        )
        high = [o for o in eligible if o.risk_tier == "high"]
        if high:
            drivers.append(
                RiskDriver(
                    kind="supplier_tier",
                    detail="High-tier suppliers present: " + ", ".join(o.supplier_code for o in high),
                    severity="medium",
                    score_contribution=8.0,
                )
            )

    events = open_risk_events(db)
    event_score = 0.0
    for ev in events:
        part = _SEV.get(ev.severity, 20.0)
        event_score += part
        drivers.append(
            RiskDriver(
                kind=ev.event_type,
                detail=ev.impact_description,
                severity=ev.severity,
                score_contribution=round(part * 0.3, 2),
            )
        )
    event_score = min(100.0, event_score) * 0.3

    wx = weather_events(db)
    wx_score = 0.0
    for w in wx:
        if w.end_date is None or True:
            wx_score += (w.disruption_factor - 1.0) * 40
            drivers.append(
                RiskDriver(
                    kind="weather",
                    detail=f"{w.event_type} in {w.region} (factor {w.disruption_factor}).",
                    severity=w.severity,
                    score_contribution=round((w.disruption_factor - 1.0) * 40 * 0.2, 2),
                )
            )
    wx_score = min(40.0, wx_score) * 0.2

    disrupted = [r for r in routes.routes if r.disrupted]
    route_part = min(20.0, 5.0 * len(disrupted))
    if disrupted:
        drivers.append(
            RiskDriver(
                kind="route_disruption",
                detail="Flagged routes: " + ", ".join(r.code for r in disrupted[:6]),
                severity="medium",
                score_contribution=round(route_part, 2),
            )
        )

    prices = latest_market_prices(db)
    fuel_mult = 1.0
    marine = [p for p in prices if p.metric == "marine_fuel_index"]
    if len(marine) >= 2:
        latest = marine[0].value
        baseline = marine[-1].value or latest
        if baseline:
            fuel_mult = round(latest / baseline, 4)
            drivers.append(
                RiskDriver(
                    kind="fuel_index",
                    detail=f"Marine fuel index {latest} vs baseline {baseline}.",
                    severity="medium" if fuel_mult > 1.08 else "low",
                    score_contribution=round(max(0, fuel_mult - 1) * 40, 2),
                )
            )

    scenario_part = 0.0
    if scenario_label and scenario_label not in {"baseline", "scenario"}:
        scenario_part = 4.0
        drivers.append(
            RiskDriver(
                kind="scenario",
                detail=scenario_label,
                severity="medium",
                score_contribution=scenario_part,
            )
        )

    rel_part = drivers[0].score_contribution if drivers else 12.0
    score = min(
        100.0,
        rel_part
        + event_score
        + wx_score
        + route_part
        + max(0, fuel_mult - 1) * 25
        + scenario_part,
    )
    notes = [
        "Risk score is a rubric over database events, reliability, weather and fuel indices.",
        "It is not an LLM-invented number.",
    ]
    return RiskResult(
        score=round(score, 1),
        drivers=drivers,
        fuel_multiplier=fuel_mult,
        notes=notes,
    )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import DecisionResponse, WhatIfBody
from app.api.service import execute_decision, to_response
from app.db.models import DecisionRun
from app.db.session import get_db
from app.scenarios.engine import scenario_from_text
from app.whatif.engine import build_patch, delivery_hours, diff_results

router = APIRouter()


@router.post("/what-if", response_model=DecisionResponse)
def run_what_if(body: WhatIfBody, db: Session = Depends(get_db)):
    parent = None
    query = body.query
    if body.run_id:
        parent = db.get(DecisionRun, body.run_id)
        if not parent:
            raise HTTPException(status_code=404, detail="baseline run not found")
        query = query or parent.query
    if not query:
        raise HTTPException(status_code=400, detail="query or run_id is required")

    constraints = None
    if body.scenario == "natural_language":
        interpreted = scenario_from_text(body.text or "")
        if not interpreted.constraints:
            raise HTTPException(
                status_code=400,
                detail="Could not interpret scenario text. Example: supplier SUP-C fails and fuel +15%.",
            )
        patch = interpreted.patch
        constraints = [item.model_dump() for item in interpreted.constraints]
    else:
        patch = build_patch(body)
    run = execute_decision(
        db,
        query,
        patch=patch.model_dump(),
        parent_id=parent.id if parent else None,
        human_constraints=constraints,
    )
    if parent:
        baseline_solver = (parent.result_json or {}).get("solver") or {}
        baseline_rec = (parent.result_json or {}).get("recommendation") or {}
        baseline_risk = (parent.result_json or {}).get("risk") or {}
        scenario_rec = (run.result_json or {}).get("recommendation") or {}
        scenario_solver = (run.result_json or {}).get("solver") or {}
        scenario_risk = (run.result_json or {}).get("risk") or {}
        baseline = {
            "total_cost": baseline_rec.get("total_cost") if baseline_rec.get("total_cost") is not None else baseline_solver.get("total_cost") or 0,
            "delivery_time_hours": delivery_hours(baseline_rec, baseline_solver),
            "risk_score": baseline_rec.get("risk_score") if baseline_rec.get("risk_score") is not None else baseline_risk.get("score") or 0,
            "unmet_demand": baseline_solver.get("unmet_demand") or 0,
        }
        scenario = {
            "total_cost": scenario_rec.get("total_cost") if scenario_rec.get("total_cost") is not None else scenario_solver.get("total_cost") or 0,
            "delivery_time_hours": delivery_hours(scenario_rec, scenario_solver),
            "risk_score": scenario_rec.get("risk_score") if scenario_rec.get("risk_score") is not None else scenario_risk.get("score") or 0,
            "unmet_demand": scenario_solver.get("unmet_demand") or 0,
        }
        what = {
            "label": patch.label,
            "patch": patch.model_dump(),
            "parent_run_id": parent.id,
            "comparison": diff_results(baseline, scenario),
        }
    else:
        what = {"label": patch.label, "patch": patch.model_dump(), "parent_run_id": None}
    return to_response(run, what_if=what)

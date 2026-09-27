from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import DecisionResponse, WhatIfBody
from app.api.service import execute_decision, to_response
from app.db.models import DecisionRun
from app.db.session import get_db
from app.whatif.engine import build_patch, diff_results

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

    patch = build_patch(body)
    run = execute_decision(db, query, patch=patch.model_dump(), parent_id=parent.id if parent else None)
    baseline_solver = {}
    if parent:
        baseline_solver = (parent.result_json or {}).get("solver") or {}
        baseline_rec = (parent.result_json or {}).get("recommendation") or {}
        baseline = {
            "total_cost": baseline_rec.get("total_cost") or baseline_solver.get("total_cost") or 0,
            "delivery_time_hours": baseline_rec.get("delivery_time_hours")
            or baseline_solver.get("delivery_time_hours")
            or 0,
            "risk_score": baseline_rec.get("risk_score")
            or ((parent.result_json or {}).get("risk") or {}).get("score")
            or 0,
            "unmet_demand": baseline_solver.get("unmet_demand") or 0,
        }
        scenario = {
            "total_cost": (run.result_json or {}).get("recommendation", {}).get("total_cost") or 0,
            "delivery_time_hours": (run.result_json or {}).get("recommendation", {}).get("delivery_time_hours")
            or 0,
            "risk_score": (run.result_json or {}).get("recommendation", {}).get("risk_score") or 0,
            "unmet_demand": ((run.result_json or {}).get("solver") or {}).get("unmet_demand") or 0,
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

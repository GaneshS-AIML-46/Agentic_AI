from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import DecisionRequest, DecisionResponse, ReviewRequest
from app.api.service import execute_decision, to_response
from app.db.models import DecisionRun
from app.db.session import get_db
from app.scenarios.engine import scenario_from_text
from app.whatif.engine import delivery_hours, diff_results

router = APIRouter()


@router.post("/decisions", response_model=DecisionResponse)
def create_decision(body: DecisionRequest, db: Session = Depends(get_db)):
    run = execute_decision(db, body.query)
    return to_response(run)


@router.get("/runs/{run_id}", response_model=DecisionResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(DecisionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return to_response(run)


def _comparison(parent: DecisionRun, child: DecisionRun) -> dict:
    parent_result = parent.result_json or {}
    child_result = child.result_json or {}

    def pack(result: dict) -> dict:
        rec = result.get("recommendation") or {}
        solver = result.get("solver") or {}
        risk = result.get("risk") or {}
        return {
            "total_cost": rec.get("total_cost") if rec.get("total_cost") is not None else solver.get("total_cost") or 0,
            "delivery_time_hours": delivery_hours(rec, solver),
            "risk_score": rec.get("risk_score") if rec.get("risk_score") is not None else risk.get("score") or 0,
            "unmet_demand": solver.get("unmet_demand") or 0,
        }

    return diff_results(pack(parent_result), pack(child_result))


@router.post("/decisions/{run_id}/review", response_model=DecisionResponse)
def review_decision(run_id: int, body: ReviewRequest, db: Session = Depends(get_db)):
    parent = db.get(DecisionRun, run_id)
    if not parent:
        raise HTTPException(status_code=404, detail="run not found")
    if body.action == "approve":
        parent.review_status = "approved"
        parent.human_feedback = body.feedback or parent.human_feedback
        result = dict(parent.result_json or {})
        result["review_status"] = "approved"
        parent.result_json = result
        db.commit()
        db.refresh(parent)
        return to_response(parent)

    scenario = scenario_from_text(body.feedback)
    if not scenario.constraints:
        raise HTTPException(
            status_code=400,
            detail="Could not translate feedback into constraints. Example: exclude supplier SUP-C and max lead time 20 days.",
        )
    child = execute_decision(
        db,
        parent.query,
        patch=scenario.patch.model_dump(),
        parent_id=parent.id,
        human_constraints=[item.model_dump() for item in scenario.constraints],
        human_feedback=body.feedback,
    )
    parent.review_status = "revised"
    db.commit()
    what = {
        "label": scenario.patch.label,
        "patch": scenario.patch.model_dump(),
        "parent_run_id": parent.id,
        "comparison": _comparison(parent, child),
    }
    return to_response(child, what_if=what)

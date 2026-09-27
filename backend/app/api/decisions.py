from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import DecisionRequest, DecisionResponse
from app.api.service import execute_decision, to_response
from app.db.models import DecisionRun
from app.db.session import get_db

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

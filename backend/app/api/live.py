from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.live.feed import apply_edit, tick

router = APIRouter()


class LiveEdit(BaseModel):
    supplier_code: str | None = None
    unit_price: float | None = Field(default=None, gt=0)
    warehouse_code: str | None = None
    on_hand: int | None = Field(default=None, ge=0)
    route_code: str | None = None
    route_status: str | None = None


@router.get("/live")
def live_snapshot(db: Session = Depends(get_db)) -> dict:
    return tick(db)


@router.patch("/live/inputs")
def edit_inputs(body: LiveEdit, db: Session = Depends(get_db)) -> dict:
    if all(
        value is None
        for value in (body.unit_price, body.on_hand, body.route_status)
    ):
        raise HTTPException(status_code=400, detail="Provide a unit price, on-hand quantity, or route status")
    try:
        return apply_edit(
            db,
            supplier_code=body.supplier_code,
            unit_price=body.unit_price,
            warehouse_code=body.warehouse_code,
            on_hand=body.on_hand,
            route_code=body.route_code,
            route_status=body.route_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

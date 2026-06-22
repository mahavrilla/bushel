"""HTTP layer for pantry 'still have it?'. Thin; delegates to pantry.service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.pantry import service
from app.pantry.schemas import PantryDecisionRequest, PantryView

router = APIRouter(prefix="/list", tags=["pantry"])


@router.get("/pantry", response_model=PantryView)
def get_pantry(db: Session = Depends(get_db)):
    view = service.get_view(db)
    db.commit()
    return view


@router.post("/items/{item_id}/pantry", response_model=PantryView)
def decide(item_id: int, body: PantryDecisionRequest, db: Session = Depends(get_db)):
    try:
        service.set_decision(db, item_id, body.keep)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view

"""HTTP layer for the staples catalog + per-trip membership."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.client import LLMClient
from app.staples import service
from app.staples.schemas import AddStapleRequest, AutoAddRequest, StapleView

router = APIRouter(tags=["staples"])


def get_llm() -> LLMClient:
    return LLMClient()


@router.get("/list/staples", response_model=StapleView)
def list_staples(db: Session = Depends(get_db)):
    view = service.get_view(db)
    db.commit()
    return view


@router.post("/staples", response_model=StapleView)
def add_staple(body: AddStapleRequest, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    service.add_staple(db, body.name, llm)
    view = service.get_view(db)
    db.commit()
    return view


@router.delete("/staples/{staple_id}", response_model=StapleView)
def remove_staple(staple_id: int, db: Session = Depends(get_db)):
    try:
        service.remove_staple(db, staple_id)
    except service.StapleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view


@router.patch("/staples/{staple_id}", response_model=StapleView)
def set_auto_add(staple_id: int, body: AutoAddRequest, db: Session = Depends(get_db)):
    try:
        service.set_auto_add(db, staple_id, body.auto_add)
    except service.StapleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view


@router.post("/list/staples/{staple_id}", response_model=StapleView)
def add_to_trip(staple_id: int, db: Session = Depends(get_db)):
    try:
        service.add_to_trip(db, staple_id)
    except service.StapleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view


@router.delete("/list/staples/{staple_id}", response_model=StapleView)
def remove_from_trip(staple_id: int, db: Session = Depends(get_db)):
    service.remove_from_trip(db, staple_id)
    view = service.get_view(db)
    db.commit()
    return view

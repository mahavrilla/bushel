"""HTTP layer for product matching + cart send. Thin; delegates to matching.service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.kroger.auth import NotConnectedError
from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError
from app.kroger.router import get_kroger_client
from app.matching import service
from app.matching.schemas import (
    ConfirmRequest,
    MatchRead,
    ProductChoice,
    SendRequest,
    SendResult,
    SetStoreRequest,
)

router = APIRouter(prefix="/list", tags=["matching"])


@router.get("/match", response_model=MatchRead)
def get_match(db: Session = Depends(get_db)):
    state = service.get_match_state(db)
    db.commit()
    return state


@router.post("/store", response_model=MatchRead)
def set_store(body: SetStoreRequest, db: Session = Depends(get_db)):
    state = service.set_store(db, body.location_id, body.name)
    db.commit()
    return state


@router.get("/items/{item_id}/products", response_model=list[ProductChoice])
def search_products(
    item_id: int,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        return service.search_item_products(db, kroger, item_id, query=q)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.NoStoreSelectedError as exc:
        raise HTTPException(status_code=409, detail={"error": "no_store", "message": str(exc)})
    except KrogerAuthError as exc:
        # Product search uses app credentials, not the user session — a 401 here means
        # misconfigured client id/secret, not an expired login. 502, like /auth/callback.
        raise HTTPException(status_code=502, detail=f"Kroger auth failed: {exc}")
    except KrogerError as exc:
        raise HTTPException(status_code=503, detail=f"Kroger unavailable: {exc}")


@router.post("/items/{item_id}/product", response_model=MatchRead)
def confirm_product(item_id: int, body: ConfirmRequest, db: Session = Depends(get_db)):
    try:
        service.confirm_product(db, item_id, body)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    state = service.get_match_state(db)
    db.commit()
    return state


@router.post("/send", response_model=SendResult)
def send(
    body: SendRequest,
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        result = service.send_to_cart(db, kroger, modality=body.modality)
    except (NotConnectedError, KrogerAuthError) as exc:
        raise HTTPException(
            status_code=409, detail={"error": "reauth_required", "message": str(exc)}
        )
    db.commit()
    return result

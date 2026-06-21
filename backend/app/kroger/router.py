"""HTTP layer for Kroger account connection + store lookup. Thin; delegates to client/auth."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.kroger import auth
from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError
from app.kroger.schemas import KrogerStatus, Location, LoginUrl

router = APIRouter(tags=["kroger"])

# Single-user local app: pending OAuth state tokens held in-process for CSRF protection.
_PENDING_STATES: set[str] = set()


def get_kroger_client() -> KrogerClient:
    return KrogerClient()


@router.get("/kroger/status", response_model=KrogerStatus)
def status(db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    row = auth.get_auth(db)
    if row is None:
        return KrogerStatus(connected=False, expired=False)
    expired = row.expires_at <= datetime.now(timezone.utc)
    return KrogerStatus(connected=True, expired=expired)


@router.get("/kroger/login", response_model=LoginUrl)
def login(kroger: KrogerClient = Depends(get_kroger_client)):
    state = secrets.token_urlsafe(16)
    _PENDING_STATES.add(state)
    return LoginUrl(url=kroger.authorize_url(state))


@router.get("/auth/callback")
def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    if state not in _PENDING_STATES:
        raise HTTPException(status_code=400, detail="invalid or expired state")
    _PENDING_STATES.discard(state)
    try:
        token = kroger.exchange_code(code)
    except KrogerError as exc:
        raise HTTPException(status_code=502, detail=f"Kroger token exchange failed: {exc}")
    auth.save_tokens(db, token)
    db.commit()
    # Send the user back to the web app (functional; Phase 6 polishes this).
    origins = get_settings().cors_origins
    return RedirectResponse(url=origins[0] if origins else "/", status_code=307)


@router.get("/kroger/locations", response_model=list[Location])
def locations(
    zip: str = Query(..., min_length=3),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        token = kroger.fetch_client_token()
        return kroger.search_locations(token.access_token, zip)
    except KrogerAuthError as exc:
        raise HTTPException(status_code=502, detail=f"Kroger auth failed: {exc}")
    except KrogerError as exc:
        raise HTTPException(status_code=503, detail=f"Kroger unavailable: {exc}")

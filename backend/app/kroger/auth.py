"""Owns the single kroger_auth row: persistence + valid-token retrieval with auto-refresh."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kroger.client import KrogerClient
from app.kroger.schemas import TokenResp
from app.models import KrogerAuth

# Refresh a little early so a token doesn't expire mid-request.
_EXPIRY_BUFFER = timedelta(seconds=60)


class NotConnectedError(Exception):
    """No Kroger tokens stored yet — the user must connect first."""


def get_auth(db: Session) -> KrogerAuth | None:
    return db.execute(select(KrogerAuth)).scalars().first()


def _expires_at(token: TokenResp) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=token.expires_in)


def save_tokens(db: Session, token: TokenResp) -> KrogerAuth:
    """Upsert the single tokens row. Keeps the existing refresh_token if a refresh
    response omits one."""
    row = get_auth(db)
    scopes = token.scope.split() if token.scope else []
    if row is None:
        row = KrogerAuth(
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
            expires_at=_expires_at(token),
            scopes=scopes,
        )
        db.add(row)
    else:
        row.access_token = token.access_token
        if token.refresh_token:
            row.refresh_token = token.refresh_token
        row.expires_at = _expires_at(token)
        if scopes:
            row.scopes = scopes
    db.flush()
    return row


def get_valid_token(db: Session, client: KrogerClient) -> str:
    """Return a non-expired customer access token, refreshing transparently.
    Raises NotConnectedError if never connected, KrogerAuthError if refresh fails."""
    row = get_auth(db)
    if row is None:
        raise NotConnectedError("Kroger account is not connected")
    if row.expires_at <= datetime.now(timezone.utc) + _EXPIRY_BUFFER:
        token = client.refresh(row.refresh_token)  # raises KrogerAuthError on failure
        row = save_tokens(db, token)
    return row.access_token

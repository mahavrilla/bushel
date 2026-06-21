from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.kroger import auth
from app.kroger.client import KrogerAuthError
from app.kroger.schemas import TokenResp
from app.models import KrogerAuth


def _save(db, access="a", refresh="r", expires_in=1800, scope="product.compact"):
    return auth.save_tokens(db, TokenResp(access_token=access, refresh_token=refresh,
                                          expires_in=expires_in, scope=scope))


def test_save_tokens_creates_single_row(db_session):
    _save(db_session)
    _save(db_session, access="a2", refresh="r2")
    rows = db_session.query(KrogerAuth).all()
    assert len(rows) == 1
    assert rows[0].access_token == "a2"


def test_get_valid_token_returns_unexpired(db_session):
    _save(db_session, access="good")
    client = MagicMock()
    assert auth.get_valid_token(db_session, client) == "good"
    client.refresh.assert_not_called()


def test_get_valid_token_refreshes_when_expired(db_session):
    row = _save(db_session, access="old", refresh="r1")
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.flush()
    client = MagicMock()
    client.refresh.return_value = TokenResp(access_token="new", refresh_token="r2", expires_in=1800)
    assert auth.get_valid_token(db_session, client) == "new"
    client.refresh.assert_called_once_with("r1")


def test_get_valid_token_not_connected_raises(db_session):
    with pytest.raises(auth.NotConnectedError):
        auth.get_valid_token(db_session, MagicMock())


def test_get_valid_token_refresh_failure_propagates(db_session):
    row = _save(db_session, refresh="r1")
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.flush()
    client = MagicMock()
    client.refresh.side_effect = KrogerAuthError("bad refresh")
    with pytest.raises(KrogerAuthError):
        auth.get_valid_token(db_session, client)

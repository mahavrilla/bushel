from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.kroger.router import get_kroger_client
from app.kroger.schemas import Location, TokenResp
from app.main import app
from app.models import KrogerAuth


def _client(db_session, kroger):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_kroger_client] = lambda: kroger
    return TestClient(app)


def test_status_disconnected(db_session):
    client = _client(db_session, MagicMock())
    resp = client.get("/kroger/status")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "expired": False}
    app.dependency_overrides.clear()


def test_status_connected(db_session):
    db_session.add(KrogerAuth(access_token="a", refresh_token="r",
                              expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db_session.flush()
    client = _client(db_session, MagicMock())
    assert client.get("/kroger/status").json() == {"connected": True, "expired": False}
    app.dependency_overrides.clear()


def test_login_returns_authorize_url(db_session):
    kroger = MagicMock()
    kroger.authorize_url.return_value = "https://api.kroger.com/v1/connect/oauth2/authorize?x=1"
    client = _client(db_session, kroger)
    body = client.get("/kroger/login").json()
    assert body["url"].startswith("https://api.kroger.com")
    app.dependency_overrides.clear()


def test_callback_exchanges_code_and_saves(db_session):
    kroger = MagicMock()
    kroger.authorize_url.return_value = "https://x/?state=STATE123"
    kroger.exchange_code.return_value = TokenResp(access_token="a", refresh_token="r", expires_in=1800)
    client = _client(db_session, kroger)
    from app.kroger import router as kr
    kr._PENDING_STATES.add("STATE123")
    resp = client.get("/auth/callback", params={"code": "c", "state": "STATE123"},
                      follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/kroger"
    assert db_session.query(KrogerAuth).count() == 1
    kroger.exchange_code.assert_called_once_with("c")
    app.dependency_overrides.clear()


def test_callback_bad_state_rejected(db_session):
    client = _client(db_session, MagicMock())
    resp = client.get("/auth/callback", params={"code": "c", "state": "nope"})
    assert resp.status_code == 400
    app.dependency_overrides.clear()


def test_locations_search(db_session):
    db_session.add(KrogerAuth(access_token="a", refresh_token="r",
                              expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db_session.flush()
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_locations.return_value = [Location(location_id="L1", name="Store", address="1 Main")]
    client = _client(db_session, kroger)
    body = client.get("/kroger/locations", params={"zip": "45202"}).json()
    assert body[0]["location_id"] == "L1"
    kroger.search_locations.assert_called_once_with("ct", "45202")
    app.dependency_overrides.clear()

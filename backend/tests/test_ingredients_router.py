from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Ingredient


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed(db_session, *names):
    for n in names:
        db_session.add(Ingredient(canonical_name=n, aliases=[]))
    db_session.flush()


def test_search_matches_substring_case_insensitive(db_session):
    _seed(db_session, "garlic", "garlic powder", "onion")
    client = _client(db_session)
    resp = client.get("/ingredients", params={"q": "GARL"})
    assert resp.status_code == 200
    names = [r["canonical_name"] for r in resp.json()]
    assert names == ["garlic", "garlic powder"]
    app.dependency_overrides.clear()


def test_search_empty_query_returns_empty(db_session):
    _seed(db_session, "garlic")
    client = _client(db_session)
    resp = client.get("/ingredients", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []
    app.dependency_overrides.clear()


def test_create_new_ingredient(db_session):
    client = _client(db_session)
    resp = client.post("/ingredients", json={"name": "Fresh Basil"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["canonical_name"] == "fresh basil"
    assert isinstance(body["id"], int)
    app.dependency_overrides.clear()


def test_create_is_idempotent_on_normalized_name(db_session):
    _seed(db_session, "basil")
    existing = db_session.query(Ingredient).filter_by(canonical_name="basil").one()
    client = _client(db_session)
    resp = client.post("/ingredients", json={"name": "Basils"})
    assert resp.status_code == 201
    assert resp.json()["id"] == existing.id
    app.dependency_overrides.clear()

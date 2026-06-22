from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.ingredients.canonicalize import CanonResult
from app.main import app
from app.models import Ingredient, Staple
from app.staples import service as staples_service
from app.staples.router import get_llm


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_llm] = lambda: MagicMock()
    return TestClient(app)


def test_add_and_list_staples(db_session, monkeypatch):
    ing = Ingredient(canonical_name="peanut butter", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    monkeypatch.setattr(staples_service, "canonicalize_names",
                        lambda names, db, llm: {names[0]: CanonResult(ingredient_id=ing.id, is_new=False)})
    client = _client(db_session)
    resp = client.post("/staples", json={"name": "peanut butter"})
    assert resp.status_code == 200
    body = client.get("/list/staples").json()
    assert any(s["ingredient_name"] == "peanut butter" for s in body["staples"])
    app.dependency_overrides.clear()


def test_toggle_auto_add_and_remove(db_session):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    s = Staple(ingredient_id=ing.id)
    db_session.add(s)
    db_session.flush()
    client = _client(db_session)
    assert client.patch(f"/staples/{s.id}", json={"auto_add": False}).status_code == 200
    db_session.refresh(s)
    assert s.auto_add is False
    assert client.delete(f"/staples/{s.id}").status_code == 200
    assert client.delete(f"/staples/{s.id}").status_code == 404
    app.dependency_overrides.clear()


def test_add_remove_on_trip(db_session):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    s = Staple(ingredient_id=ing.id, auto_add=False)
    db_session.add(s)
    db_session.flush()
    client = _client(db_session)
    assert client.post(f"/list/staples/{s.id}").status_code == 200
    body = client.get("/list/staples").json()
    assert next(x for x in body["staples"] if x["id"] == s.id)["on_trip"] is True
    assert client.delete(f"/list/staples/{s.id}").status_code == 200
    app.dependency_overrides.clear()

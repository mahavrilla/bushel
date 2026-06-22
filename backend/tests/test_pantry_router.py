from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.matching.service import _kept_items
from app.models import GroceryList, GroceryListItem, Ingredient, PurchaseLog


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed(db, *, days_ago=None):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=2.0, total_unit="lb",
                           pantry_status="needed")
    db.add(item)
    if days_ago is not None:
        db.add(PurchaseLog(ingredient_id=ing.id, kroger_upc="0001", qty=2.0, unit="lb",
                           purchased_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
    db.flush()
    return gl, ing, item


def test_get_pantry_flags_recent(db_session):
    gl, ing, item = _seed(db_session, days_ago=5)
    client = _client(db_session)
    body = client.get("/list/pantry").json()
    flagged = next(i for i in body["items"] if i["item_id"] == item.id)
    assert flagged["pantry_status"] == "maybe_have"
    assert flagged["days_ago"] == 5
    app.dependency_overrides.clear()


def test_post_pantry_skip_excludes_from_kept(db_session):
    gl, ing, item = _seed(db_session, days_ago=5)
    client = _client(db_session)
    resp = client.post(f"/list/items/{item.id}/pantry", json={"keep": False})
    assert resp.status_code == 200
    assert _kept_items(db_session, gl.id) == []
    app.dependency_overrides.clear()


def test_post_pantry_keep_resolves(db_session):
    gl, ing, item = _seed(db_session, days_ago=5)
    client = _client(db_session)
    resp = client.post(f"/list/items/{item.id}/pantry", json={"keep": True})
    assert resp.status_code == 200
    db_session.refresh(item)
    assert item.pantry_status == "needed"
    assert item.pantry_resolved is True
    app.dependency_overrides.clear()


def test_post_pantry_unknown_item_404(db_session):
    client = _client(db_session)
    resp = client.post("/list/items/9999/pantry", json={"keep": True})
    assert resp.status_code == 404
    app.dependency_overrides.clear()

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Ingredient, Recipe, RecipeIngredient


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed_recipe(db_session, title="R", default_servings=2):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(ing)
    db_session.flush()
    r = Recipe(title=title, default_servings=default_servings)
    db_session.add(r)
    db_session.flush()
    db_session.add(RecipeIngredient(
        recipe_id=r.id, raw_text="1 cup flour", qty=1.0, unit="cup",
        ingredient_id=ing.id, parse_source="library", needs_review=False,
    ))
    db_session.flush()
    return r, ing


def test_get_list_creates_empty_draft(db_session):
    client = _client(db_session)
    resp = client.get("/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "draft"
    assert body["recipes"] == []
    assert body["items"] == []
    app.dependency_overrides.clear()


def test_add_recipe_returns_consolidated_list(db_session):
    r, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.post("/list/recipes", json={"recipe_id": r.id, "servings": 4})
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipes"][0]["recipe_id"] == r.id
    assert body["recipes"][0]["servings"] == 4
    item = body["items"][0]
    assert item["ingredient_name"] == "flour"
    assert item["category"] == "baking"
    assert item["quantities"] == [{"qty": 2.0, "unit": "cup"}]
    app.dependency_overrides.clear()


def test_patch_servings(db_session):
    r, ing = _seed_recipe(db_session)
    client = _client(db_session)
    client.post("/list/recipes", json={"recipe_id": r.id})
    resp = client.patch(f"/list/recipes/{r.id}", json={"servings": 6})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["quantities"] == [{"qty": 3.0, "unit": "cup"}]
    app.dependency_overrides.clear()


def test_patch_missing_recipe_404(db_session):
    client = _client(db_session)
    client.get("/list")
    resp = client.patch("/list/recipes/9999", json={"servings": 4})
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_delete_recipe(db_session):
    r, ing = _seed_recipe(db_session)
    client = _client(db_session)
    client.post("/list/recipes", json={"recipe_id": r.id})
    resp = client.delete(f"/list/recipes/{r.id}")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    app.dependency_overrides.clear()

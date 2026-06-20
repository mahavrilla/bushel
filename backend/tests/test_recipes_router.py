from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Ingredient, Recipe, RecipeIngredient


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed_recipe(db_session):
    ing = Ingredient(canonical_name="egg", aliases=[])
    db_session.add(ing)
    db_session.flush()
    recipe = Recipe(title="Test", default_servings=2)
    db_session.add(recipe)
    db_session.flush()
    ri = RecipeIngredient(
        recipe_id=recipe.id, raw_text="1 egg", qty=1.0, unit=None,
        ingredient_id=ing.id, parse_source="library", needs_review=True,
    )
    db_session.add(ri)
    db_session.flush()
    return recipe, ri, ing


def test_get_recipe_returns_ingredients(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.get(f"/recipes/{recipe.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test"
    assert body["ingredients"][0]["ingredient_name"] == "egg"
    assert body["ingredients"][0]["needs_review"] is True
    app.dependency_overrides.clear()


def test_list_recipes(db_session):
    _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.get("/recipes")
    assert resp.status_code == 200
    assert resp.json()[0]["title"] == "Test"
    app.dependency_overrides.clear()


def test_patch_ingredient_clears_flag(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.patch(f"/recipes/{recipe.id}/ingredients/{ri.id}", json={"qty": 2.0})
    assert resp.status_code == 200
    db_session.refresh(ri)
    assert ri.qty == 2.0
    assert ri.needs_review is False
    app.dependency_overrides.clear()


def test_manual_create_endpoint(db_session):
    client = _client(db_session)
    with patch("app.recipes.router.create_from_manual") as mock_create:
        recipe = Recipe(title="Manual", default_servings=1)
        db_session.add(recipe)
        db_session.flush()
        mock_create.return_value = recipe
        resp = client.post("/recipes", json={"title": "Manual", "servings": 1, "raw_lines": ["1 egg"]})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Manual"
    app.dependency_overrides.clear()


def test_import_endpoint(db_session):
    client = _client(db_session)
    with patch("app.recipes.router.import_from_url") as mock_import:
        recipe = Recipe(title="Imported", default_servings=4, source_url="https://x.com")
        db_session.add(recipe)
        db_session.flush()
        mock_import.return_value = recipe
        resp = client.post("/recipes/import", json={"url": "https://x.com"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Imported"
    app.dependency_overrides.clear()

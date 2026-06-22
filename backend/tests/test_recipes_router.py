from unittest.mock import ANY, patch

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import GroceryList, GroceryListItem, GroceryListRecipe, Ingredient, Recipe, RecipeIngredient


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


def test_delete_recipe_removes_it(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}")
    assert resp.status_code == 204
    assert db_session.get(Recipe, recipe.id) is None
    app.dependency_overrides.clear()


def test_delete_recipe_404_when_missing(db_session):
    client = _client(db_session)
    resp = client.delete("/recipes/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_add_ingredient_endpoint(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    with patch("app.recipes.router.add_ingredient") as mock_add:
        mock_add.return_value = recipe
        resp = client.post(f"/recipes/{recipe.id}/ingredients", json={"raw_text": "2 cups flour"})
    assert resp.status_code == 201
    assert resp.json()["id"] == recipe.id
    mock_add.assert_called_once_with(db_session, recipe.id, "2 cups flour", ANY)
    app.dependency_overrides.clear()


def test_add_ingredient_404_when_recipe_missing(db_session):
    from app.recipes.service import RecipeNotFoundError

    client = _client(db_session)
    with patch("app.recipes.router.add_ingredient", side_effect=RecipeNotFoundError("nope")):
        resp = client.post("/recipes/99999/ingredients", json={"raw_text": "1 egg"})
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_add_ingredient_blank_is_422(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.post(f"/recipes/{recipe.id}/ingredients", json={"raw_text": "   "})
    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_delete_ingredient_endpoint(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}/ingredients/{ri.id}")
    assert resp.status_code == 200
    assert resp.json()["ingredients"] == []
    assert db_session.get(RecipeIngredient, ri.id) is None
    app.dependency_overrides.clear()


def test_delete_ingredient_404_when_missing(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}/ingredients/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_delete_ingredient_404_when_on_other_recipe(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    other = Recipe(title="Other", default_servings=1)
    db_session.add(other)
    db_session.flush()
    client = _client(db_session)
    resp = client.delete(f"/recipes/{other.id}/ingredients/{ri.id}")
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_delete_recipe_on_list_recomputes_draft(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    draft = GroceryList(name="Draft", status="draft")
    db_session.add(draft)
    db_session.flush()
    db_session.add(GroceryListRecipe(list_id=draft.id, recipe_id=recipe.id, servings=2))
    db_session.add(
        GroceryListItem(list_id=draft.id, ingredient_id=ing.id, source_recipe_ids=[recipe.id])
    )
    db_session.flush()
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}")
    assert resp.status_code == 204
    remaining = (
        db_session.query(GroceryListItem).filter_by(list_id=draft.id).count()
    )
    assert remaining == 0
    assert (
        db_session.query(GroceryListRecipe).filter_by(recipe_id=recipe.id).count() == 0
    )
    app.dependency_overrides.clear()

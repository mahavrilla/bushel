import pytest

from app.models import (
    GroceryList,
    GroceryListItem,
    GroceryListRecipe,
    Ingredient,
    IngredientProductMap,
    KrogerAuth,
    PurchaseLog,
    Recipe,
    RecipeIngredient,
)


def test_all_models_have_tablenames():
    expected = {
        Recipe: "recipes",
        RecipeIngredient: "recipe_ingredients",
        Ingredient: "ingredients",
        IngredientProductMap: "ingredient_product_map",
        GroceryList: "grocery_lists",
        GroceryListItem: "grocery_list_items",
        GroceryListRecipe: "grocery_list_recipes",
        PurchaseLog: "purchase_log",
        KrogerAuth: "kroger_auth",
    }
    for model, table in expected.items():
        assert model.__tablename__ == table


def test_ingredient_has_canonical_name_and_aliases():
    cols = Ingredient.__table__.columns
    assert "canonical_name" in cols
    assert "aliases" in cols


def test_grocery_list_item_tracks_total_and_purchase_qty():
    cols = GroceryListItem.__table__.columns
    assert "total_qty" in cols
    assert "purchase_qty" in cols
    assert "pantry_status" in cols


def test_array_columns_default_to_empty_list(db_session):
    """
    Regression test: Ingredient.aliases uses default=list (Python-side) with no server_default.
    Verify that inserting without explicitly setting aliases results in [] (not a NOT NULL error).
    This proves the ORM applies the Python default on INSERT, so no server_default is required.
    """
    # Insert WITHOUT setting aliases
    ing = Ingredient(canonical_name="salt_test_array_default")
    db_session.add(ing)
    db_session.flush()
    db_session.expire_all()

    fetched = db_session.get(Ingredient, ing.id)
    assert fetched.aliases == [], (
        f"Expected aliases == [], got {fetched.aliases!r}. "
        "The Python-side default=list should be applied by the ORM on INSERT."
    )


def test_ingredient_round_trips(db_session):
    ing = Ingredient(canonical_name="all-purpose flour", aliases=["AP flour", "plain flour"])
    db_session.add(ing)
    db_session.flush()
    db_session.expire_all()

    fetched = db_session.get(Ingredient, ing.id)
    assert fetched is not None
    assert fetched.canonical_name == "all-purpose flour"
    assert fetched.aliases == ["AP flour", "plain flour"]


def test_recipe_ingredient_has_needs_review():
    from app.models import RecipeIngredient

    cols = RecipeIngredient.__table__.columns
    assert "needs_review" in cols
    assert cols["needs_review"].default.arg is False


def test_grocery_list_recipe_model():
    from app.models import GroceryListRecipe

    cols = GroceryListRecipe.__table__.columns
    assert GroceryListRecipe.__tablename__ == "grocery_list_recipes"
    assert {"id", "list_id", "recipe_id", "servings"} <= set(cols.keys())
    uniques = [c for c in GroceryListRecipe.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert any({col.name for col in u.columns} == {"list_id", "recipe_id"} for u in uniques)


def test_grocery_list_item_has_quantities():
    from app.models import GroceryListItem

    assert "quantities" in GroceryListItem.__table__.columns


def test_grocery_list_item_has_purchase_qty_estimated_default_false(db_session):
    from app.models import GroceryList, GroceryListItem, Ingredient

    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(ing)
    db_session.flush()
    gl = GroceryList(name="Draft", status="draft")
    db_session.add(gl)
    db_session.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id)
    db_session.add(item)
    db_session.flush()
    assert item.purchase_qty_estimated is False


def test_grocery_list_item_pantry_resolved_defaults_false(db_session):
    from app.models import GroceryList, GroceryListItem, Ingredient

    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    gl = GroceryList(name="Draft", status="draft")
    db_session.add(gl)
    db_session.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id)
    db_session.add(item)
    db_session.flush()
    assert item.pantry_resolved is False

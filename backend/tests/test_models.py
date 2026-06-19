import pytest

from app.models import (
    GroceryList,
    GroceryListItem,
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

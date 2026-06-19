import os

import pytest

from app.db import Base, SessionLocal, engine
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


def test_array_columns_default_to_empty_list():
    """
    Regression test: Ingredient.aliases uses default=list (Python-side) with no server_default.
    Verify that inserting without explicitly setting aliases results in [] (not a NOT NULL error).
    This proves the ORM applies the Python default on INSERT, so no server_default is required.
    """
    # Ensure tables exist
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        # Clean up any leftover test data from prior runs
        session.query(Ingredient).filter_by(canonical_name="salt_test_array_default").delete()
        session.commit()

        # Insert WITHOUT setting aliases
        ing = Ingredient(canonical_name="salt_test_array_default")
        session.add(ing)
        session.commit()

        # Query it back fresh
        fetched = session.query(Ingredient).filter_by(canonical_name="salt_test_array_default").one()
        assert fetched.aliases == [], (
            f"Expected aliases == [], got {fetched.aliases!r}. "
            "The Python-side default=list should be applied by the ORM on INSERT."
        )

        # Clean up
        session.delete(fetched)
        session.commit()


from app.models import Ingredient as _Ingredient


def test_ingredient_round_trips(db_session):
    ing = _Ingredient(canonical_name="all-purpose flour", aliases=["AP flour", "plain flour"])
    db_session.add(ing)
    db_session.flush()

    fetched = db_session.get(_Ingredient, ing.id)
    assert fetched is not None
    assert fetched.canonical_name == "all-purpose flour"
    assert "AP flour" in fetched.aliases

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

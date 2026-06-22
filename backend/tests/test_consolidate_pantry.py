from app.consolidate import service
from app.models import GroceryListItem, Ingredient, Recipe, RecipeIngredient


def _recipe(db, title, ingredient):
    r = Recipe(title=title, default_servings=2)
    db.add(r)
    db.flush()
    db.add(RecipeIngredient(recipe_id=r.id, raw_text="1 cup flour", qty=1.0, unit="cup",
                            ingredient_id=ingredient.id, parse_source="library", needs_review=False))
    db.flush()
    return r


def test_recompute_preserves_pantry_decision(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(flour)
    db_session.flush()
    r1 = _recipe(db_session, "Pancakes", flour)
    service.add_recipe(db_session, r1.id, 2)

    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    item.pantry_status = "skipped"
    item.pantry_resolved = True
    db_session.flush()

    # Adding another recipe triggers a full _recompute (delete + rebuild).
    r2 = _recipe(db_session, "Bread", flour)
    service.add_recipe(db_session, r2.id, 2)

    rebuilt = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert rebuilt.pantry_status == "skipped"
    assert rebuilt.pantry_resolved is True


def test_recompute_new_ingredient_starts_needed_unresolved(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(flour)
    db_session.flush()
    r1 = _recipe(db_session, "Pancakes", flour)
    service.add_recipe(db_session, r1.id, 2)
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert item.pantry_status == "needed"
    assert item.pantry_resolved is False

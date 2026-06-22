from app.consolidate import service
from app.models import (
    GroceryListItem,
    GroceryListStaple,
    Ingredient,
    Recipe,
    RecipeIngredient,
    Staple,
)


def _recipe(db, title, ingredient):
    r = Recipe(title=title, default_servings=2)
    db.add(r)
    db.flush()
    db.add(RecipeIngredient(recipe_id=r.id, raw_text="1 cup flour", qty=1.0, unit="cup",
                            ingredient_id=ingredient.id, parse_source="library", needs_review=False))
    db.flush()
    return r


def test_recompute_includes_linked_staple_as_item(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[], category="baking")
    pb = Ingredient(canonical_name="peanut butter", aliases=[], category="pantry")
    db_session.add_all([flour, pb])
    db_session.flush()
    r = _recipe(db_session, "Pancakes", flour)
    service.add_recipe(db_session, r.id, 2)

    staple = Staple(ingredient_id=pb.id)
    db_session.add(staple)
    db_session.flush()
    draft = service.get_or_create_draft(db_session)
    db_session.add(GroceryListStaple(list_id=draft.id, staple_id=staple.id))
    db_session.flush()

    service.recompute_draft(db_session)
    ids = {it.ingredient_id for it in db_session.query(GroceryListItem).filter_by(list_id=draft.id)}
    assert pb.id in ids
    assert flour.id in ids


def test_recompute_staple_only_item_has_empty_sources(db_session):
    pb = Ingredient(canonical_name="peanut butter", aliases=[], category="pantry")
    db_session.add(pb)
    db_session.flush()
    draft = service.get_or_create_draft(db_session)
    staple = Staple(ingredient_id=pb.id)
    db_session.add(staple)
    db_session.flush()
    db_session.add(GroceryListStaple(list_id=draft.id, staple_id=staple.id))
    db_session.flush()

    service.recompute_draft(db_session)
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=pb.id).one()
    assert item.source_recipe_ids == []

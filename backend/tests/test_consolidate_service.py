import pytest

from app.consolidate.service import (
    NotOnListError,
    add_recipe,
    get_or_create_draft,
    remove_recipe,
    set_servings,
)
from app.models import GroceryListItem, GroceryListRecipe, Ingredient, Recipe, RecipeIngredient


def _recipe(db, title, default_servings, lines):
    """lines = [(qty, unit, ingredient_row)]"""
    r = Recipe(title=title, default_servings=default_servings)
    db.add(r)
    db.flush()
    for qty, unit, ing in lines:
        db.add(RecipeIngredient(
            recipe_id=r.id, raw_text=f"{qty} {unit} {ing.canonical_name}", qty=qty, unit=unit,
            ingredient_id=ing.id, parse_source="library", needs_review=False,
        ))
    db.flush()
    return r


def test_get_or_create_draft_is_singleton(db_session):
    a = get_or_create_draft(db_session)
    b = get_or_create_draft(db_session)
    assert a.id == b.id
    assert a.status == "draft"


def test_add_recipe_scales_and_consolidates(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    egg = Ingredient(canonical_name="egg", aliases=[])
    db_session.add_all([flour, egg])
    db_session.flush()
    pancakes = _recipe(db_session, "Pancakes", 4, [(2.0, "cup", flour), (2.0, None, egg)])
    bread = _recipe(db_session, "Bread", 2, [(1.0, "cup", flour)])

    add_recipe(db_session, pancakes.id, servings=6)   # factor 1.5 → 3 cups flour, 3 eggs
    draft = add_recipe(db_session, bread.id, servings=2)  # factor 1.0 → +1 cup flour

    items = db_session.query(GroceryListItem).filter_by(list_id=draft.id).all()
    by_ing = {i.ingredient_id: i for i in items}
    flour_item = by_ing[flour.id]
    assert flour_item.quantities == [{"qty": 4.0, "unit": "cup"}]
    assert flour_item.total_qty == 4.0 and flour_item.total_unit == "cup"
    assert sorted(flour_item.source_recipe_ids) == sorted([pancakes.id, bread.id])
    assert by_ing[egg.id].quantities == [{"qty": 3.0, "unit": None}]


def test_add_recipe_upserts_servings(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 2, [(1.0, "cup", flour)])

    add_recipe(db_session, r.id, servings=2)
    add_recipe(db_session, r.id, servings=4)  # upsert

    memberships = db_session.query(GroceryListRecipe).filter_by(recipe_id=r.id).all()
    assert len(memberships) == 1
    assert memberships[0].servings == 4
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert item.quantities == [{"qty": 2.0, "unit": "cup"}]


def test_rebuild_is_idempotent(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 1, [(1.0, "cup", flour)])
    add_recipe(db_session, r.id, servings=1)
    first = db_session.query(GroceryListItem).count()
    set_servings(db_session, r.id, 1)
    assert db_session.query(GroceryListItem).count() == first


def test_remove_recipe(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 1, [(1.0, "cup", flour)])
    add_recipe(db_session, r.id, servings=1)
    draft = remove_recipe(db_session, r.id)
    assert db_session.query(GroceryListItem).filter_by(list_id=draft.id).count() == 0


def test_set_servings_missing_recipe_raises(db_session):
    get_or_create_draft(db_session)
    with pytest.raises(NotOnListError):
        set_servings(db_session, 9999, 4)


def test_zero_default_servings_does_not_divide_by_zero(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 0, [(1.0, "cup", flour)])  # default_servings 0
    add_recipe(db_session, r.id, servings=3)  # guarded → treat default as 1 → 3 cups
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert item.quantities == [{"qty": 3.0, "unit": "cup"}]

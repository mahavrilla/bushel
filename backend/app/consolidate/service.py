"""Draft grocery list management + delete-and-rebuild consolidation.

The only writer of grocery_list_recipes and grocery_list_items.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.consolidate.units import consolidate
from app.models import (
    GroceryList,
    GroceryListItem,
    GroceryListRecipe,
    Recipe,
    RecipeIngredient,
)


class NotOnListError(Exception):
    """Raised when a recipe targeted by patch/remove is not on the draft list."""


def get_or_create_draft(db: Session) -> GroceryList:
    draft = db.execute(
        select(GroceryList).where(GroceryList.status == "draft").order_by(GroceryList.id.desc())
    ).scalars().first()
    if draft is None:
        draft = GroceryList(name="Draft", status="draft")
        db.add(draft)
        db.flush()
    return draft


def _membership(db: Session, list_id: int, recipe_id: int) -> GroceryListRecipe | None:
    return db.execute(
        select(GroceryListRecipe).where(
            GroceryListRecipe.list_id == list_id, GroceryListRecipe.recipe_id == recipe_id
        )
    ).scalars().first()


def _recompute(db: Session, draft: GroceryList) -> None:
    """Delete the list's items and rebuild them from its recipe memberships."""
    # Preserve per-ingredient user pantry decisions across the delete-and-rebuild.
    prior = {
        it.ingredient_id: (it.pantry_status, it.pantry_resolved)
        for it in db.execute(
            select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
        ).scalars().all()
    }

    db.execute(delete(GroceryListItem).where(GroceryListItem.list_id == draft.id))

    memberships = db.execute(
        select(GroceryListRecipe).where(GroceryListRecipe.list_id == draft.id)
    ).scalars().all()

    grouped: dict[int, dict] = defaultdict(lambda: {"quantities": [], "recipes": set()})

    for m in memberships:
        recipe = db.get(Recipe, m.recipe_id)
        default = recipe.default_servings or 1
        factor = m.servings / default
        rows = db.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == m.recipe_id,
                RecipeIngredient.ingredient_id.is_not(None),
            )
        ).scalars().all()
        for row in rows:
            scaled = row.qty * factor if row.qty is not None else None
            grouped[row.ingredient_id]["quantities"].append((scaled, row.unit))
            grouped[row.ingredient_id]["recipes"].add(m.recipe_id)

    for ingredient_id, data in grouped.items():
        quantities = consolidate(data["quantities"])
        single = quantities[0] if len(quantities) == 1 else None
        status, resolved = prior.get(ingredient_id, ("needed", False))
        db.add(
            GroceryListItem(
                list_id=draft.id,
                ingredient_id=ingredient_id,
                quantities=quantities,
                total_qty=single["qty"] if single else None,
                total_unit=single["unit"] if single else None,
                source_recipe_ids=sorted(data["recipes"]),
                pantry_status=status,
                pantry_resolved=resolved,
            )
        )
    db.flush()


def add_recipe(db: Session, recipe_id: int, servings: int | None = None) -> GroceryList:
    draft = get_or_create_draft(db)
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise NotOnListError(f"recipe {recipe_id} does not exist")
    target = servings if servings is not None else (recipe.default_servings or 1)
    existing = _membership(db, draft.id, recipe_id)
    if existing is not None:
        existing.servings = target
    else:
        db.add(GroceryListRecipe(list_id=draft.id, recipe_id=recipe_id, servings=target))
    db.flush()
    _recompute(db, draft)
    return draft


def set_servings(db: Session, recipe_id: int, servings: int) -> GroceryList:
    draft = get_or_create_draft(db)
    existing = _membership(db, draft.id, recipe_id)
    if existing is None:
        raise NotOnListError(f"recipe {recipe_id} not on list")
    existing.servings = servings
    db.flush()
    _recompute(db, draft)
    return draft


def remove_recipe(db: Session, recipe_id: int) -> GroceryList:
    draft = get_or_create_draft(db)
    existing = _membership(db, draft.id, recipe_id)
    if existing is None:
        raise NotOnListError(f"recipe {recipe_id} not on list")
    db.delete(existing)
    db.flush()
    _recompute(db, draft)
    return draft

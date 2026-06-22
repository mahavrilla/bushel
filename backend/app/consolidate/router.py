"""HTTP layer for the draft grocery list. Thin — delegates to the service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consolidate.schemas import (
    AddRecipeRequest,
    ListItemRead,
    ListRead,
    ListRecipeRead,
    SetServingsRequest,
    SubQuantity,
)
from app.consolidate.service import (
    NotOnListError,
    add_recipe,
    get_or_create_draft,
    remove_recipe,
    set_servings,
)
from app.db import get_db
from app.models import (
    GroceryList,
    GroceryListItem,
    GroceryListRecipe,
    Ingredient,
    Recipe,
)

router = APIRouter(prefix="/list", tags=["list"])

_CATEGORY_ORDER = [
    "produce", "meat", "dairy", "baking", "pantry", "frozen", "beverage", "spice", "other",
]


def _serialize(draft: GroceryList, db: Session) -> ListRead:
    memberships = db.execute(
        select(GroceryListRecipe).where(GroceryListRecipe.list_id == draft.id)
    ).scalars().all()
    recipe_by_id = {r.id: r for r in db.execute(select(Recipe)).scalars().all()}
    recipes = [
        ListRecipeRead(
            recipe_id=m.recipe_id,
            title=recipe_by_id[m.recipe_id].title,
            servings=m.servings,
            default_servings=recipe_by_id[m.recipe_id].default_servings,
        )
        for m in memberships
    ]

    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    rows = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
    ).scalars().all()

    def cat_key(item: GroceryListItem):
        cat = ing_by_id[item.ingredient_id].category
        order = _CATEGORY_ORDER.index(cat) if cat in _CATEGORY_ORDER else len(_CATEGORY_ORDER)
        return (order, ing_by_id[item.ingredient_id].canonical_name)

    items = [
        ListItemRead(
            item_id=r.id,
            ingredient_id=r.ingredient_id,
            ingredient_name=ing_by_id[r.ingredient_id].canonical_name,
            category=ing_by_id[r.ingredient_id].category,
            quantities=[SubQuantity(**q) for q in r.quantities],
            source_recipe_ids=r.source_recipe_ids,
            pantry_status=r.pantry_status,
        )
        for r in sorted(rows, key=cat_key)
    ]
    return ListRead(id=draft.id, status=draft.status, recipes=recipes, items=items)


@router.get("", response_model=ListRead)
def get_list(db: Session = Depends(get_db)):
    draft = get_or_create_draft(db)
    db.commit()
    return _serialize(draft, db)


@router.post("/recipes", response_model=ListRead)
def add_recipe_endpoint(body: AddRecipeRequest, db: Session = Depends(get_db)):
    try:
        draft = add_recipe(db, body.recipe_id, body.servings)
    except NotOnListError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(draft, db)


@router.patch("/recipes/{recipe_id}", response_model=ListRead)
def set_servings_endpoint(recipe_id: int, body: SetServingsRequest, db: Session = Depends(get_db)):
    try:
        draft = set_servings(db, recipe_id, body.servings)
    except NotOnListError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(draft, db)


@router.delete("/recipes/{recipe_id}", response_model=ListRead)
def remove_recipe_endpoint(recipe_id: int, db: Session = Depends(get_db)):
    try:
        draft = remove_recipe(db, recipe_id)
    except NotOnListError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(draft, db)

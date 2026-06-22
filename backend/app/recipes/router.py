"""HTTP layer for recipes. Thin — delegates to the service and serializes models."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.client import LLMClient, LLMUnavailableError
from app.models import Ingredient, Recipe, RecipeIngredient
from app.recipes.scraper import ScrapeError
from app.recipes.schemas import (
    AddIngredientRequest,
    ExtractedIngredients,
    ExtractIngredientsRequest,
    IngredientRead,
    IngredientUpdate,
    ImportRequest,
    ManualRecipeRequest,
    RecipeRead,
    RecipeSummary,
)
from app.consolidate.units import normalize_unit
from app.recipes.service import (
    RecipeNotFoundError,
    add_ingredient,
    create_from_manual,
    delete_recipe,
    extract_ingredient_lines,
    import_from_url,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


def get_llm() -> LLMClient:
    return LLMClient()


def _serialize(recipe: Recipe, db: Session) -> RecipeRead:
    rows = db.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).scalars().all()
    name_by_id = {
        i.id: i.canonical_name
        for i in db.execute(select(Ingredient)).scalars().all()
    }
    ingredients = [
        IngredientRead(
            id=r.id,
            raw_text=r.raw_text,
            qty=r.qty,
            unit=r.unit,
            ingredient_id=r.ingredient_id,
            ingredient_name=name_by_id.get(r.ingredient_id),
            parse_source=r.parse_source,
            needs_review=r.needs_review,
        )
        for r in rows
    ]
    return RecipeRead(
        id=recipe.id,
        title=recipe.title,
        servings=recipe.default_servings,
        source_url=recipe.source_url,
        ingredients=ingredients,
    )


@router.post("/import", response_model=RecipeRead, status_code=201)
def import_recipe(body: ImportRequest, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    try:
        recipe = import_from_url(body.url, db=db, llm=llm)
    except ScrapeError as exc:
        raise HTTPException(status_code=422, detail=f"Could not import recipe: {exc}")
    db.commit()
    return _serialize(recipe, db)


@router.post("", response_model=RecipeRead, status_code=201)
def create_recipe(body: ManualRecipeRequest, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    if not body.raw_lines:
        raise HTTPException(status_code=422, detail="At least one ingredient line is required")
    recipe = create_from_manual(
        title=body.title, servings=body.servings, raw_lines=body.raw_lines, db=db, llm=llm
    )
    db.commit()
    return _serialize(recipe, db)


@router.post("/extract-ingredients", response_model=ExtractedIngredients)
def extract_ingredients_endpoint(
    body: ExtractIngredientsRequest, llm: LLMClient = Depends(get_llm)
):
    try:
        lines = extract_ingredient_lines(body.text, llm)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Ingredient extraction unavailable: {exc}")
    return ExtractedIngredients(lines=lines)


@router.post("/{recipe_id}/ingredients", response_model=RecipeRead, status_code=201)
def add_ingredient_endpoint(
    recipe_id: int,
    body: AddIngredientRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    try:
        recipe = add_ingredient(db, recipe_id, body.raw_text, llm)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(recipe, db)


@router.get("", response_model=list[RecipeSummary])
def list_recipes(db: Session = Depends(get_db)):
    recipes = db.execute(select(Recipe).order_by(Recipe.created_at.desc())).scalars().all()
    return [RecipeSummary(id=r.id, title=r.title, servings=r.default_servings) for r in recipes]


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _serialize(recipe, db)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe_endpoint(recipe_id: int, db: Session = Depends(get_db)):
    try:
        delete_recipe(db, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()


@router.delete("/{recipe_id}/ingredients/{ingredient_row_id}", response_model=RecipeRead)
def delete_ingredient(recipe_id: int, ingredient_row_id: int, db: Session = Depends(get_db)):
    row = db.get(RecipeIngredient, ingredient_row_id)
    if row is None or row.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    db.delete(row)
    db.commit()
    recipe = db.get(Recipe, recipe_id)
    return _serialize(recipe, db)


@router.patch("/{recipe_id}/ingredients/{ingredient_row_id}", response_model=RecipeRead)
def update_ingredient(
    recipe_id: int, ingredient_row_id: int, body: IngredientUpdate, db: Session = Depends(get_db)
):
    row = db.get(RecipeIngredient, ingredient_row_id)
    if row is None or row.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if body.qty is not None:
        row.qty = body.qty
    if body.unit is not None:
        row.unit = normalize_unit(body.unit)
    if body.ingredient_id is not None:
        row.ingredient_id = body.ingredient_id
    row.needs_review = False
    db.commit()
    recipe = db.get(Recipe, recipe_id)
    return _serialize(recipe, db)

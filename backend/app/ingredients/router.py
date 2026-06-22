"""HTTP layer for searching and creating canonical ingredients."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingredients.normalize import normalize_name
from app.ingredients.schemas import CreateIngredientRequest, IngredientOption
from app.models import Ingredient

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientOption])
def search_ingredients(q: str = "", db: Session = Depends(get_db)):
    if not q.strip():
        return []
    rows = db.execute(
        select(Ingredient)
        .where(Ingredient.canonical_name.ilike(f"%{q.strip()}%"))
        .order_by(Ingredient.canonical_name)
        .limit(20)
    ).scalars().all()
    return [IngredientOption(id=i.id, canonical_name=i.canonical_name) for i in rows]


@router.post("", response_model=IngredientOption, status_code=201)
def create_ingredient(body: CreateIngredientRequest, db: Session = Depends(get_db)):
    normalized = normalize_name(body.name)
    existing = db.execute(
        select(Ingredient).where(Ingredient.canonical_name == normalized)
    ).scalars().first()
    if existing is None:
        existing = Ingredient(canonical_name=normalized, aliases=[])
        db.add(existing)
        db.commit()
        db.refresh(existing)
    return IngredientOption(id=existing.id, canonical_name=existing.canonical_name)

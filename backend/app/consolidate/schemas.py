"""Pydantic request/response models for the consolidation (grocery list) API."""

from __future__ import annotations

from pydantic import BaseModel


class AddRecipeRequest(BaseModel):
    recipe_id: int
    servings: int | None = None


class SetServingsRequest(BaseModel):
    servings: int


class SubQuantity(BaseModel):
    qty: float | None
    unit: str | None


class ListItemRead(BaseModel):
    ingredient_id: int
    ingredient_name: str | None
    category: str | None
    quantities: list[SubQuantity]
    source_recipe_ids: list[int]
    pantry_status: str


class ListRecipeRead(BaseModel):
    recipe_id: int
    title: str
    servings: int
    default_servings: int


class ListRead(BaseModel):
    id: int
    status: str
    recipes: list[ListRecipeRead]
    items: list[ListItemRead]

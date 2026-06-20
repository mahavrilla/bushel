"""Pydantic request/response models for the recipes API."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class ImportRequest(BaseModel):
    url: str


class ManualRecipeRequest(BaseModel):
    title: str
    servings: int = 1
    raw_lines: list[str]

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()

    @field_validator("raw_lines")
    @classmethod
    def _drop_blank_lines(cls, v: list[str]) -> list[str]:
        return [line.strip() for line in v if line.strip()]


class IngredientUpdate(BaseModel):
    qty: float | None = None
    unit: str | None = None
    name: str | None = None
    ingredient_id: int | None = None


class IngredientRead(BaseModel):
    id: int
    raw_text: str
    qty: float | None
    unit: str | None
    ingredient_id: int | None
    ingredient_name: str | None
    parse_source: str
    needs_review: bool


class RecipeRead(BaseModel):
    id: int
    title: str
    servings: int
    source_url: str | None
    ingredients: list[IngredientRead]


class RecipeSummary(BaseModel):
    id: int
    title: str
    servings: int

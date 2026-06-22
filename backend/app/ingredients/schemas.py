"""Pydantic models for the ingredients API."""

from __future__ import annotations

from pydantic import BaseModel


class IngredientOption(BaseModel):
    id: int
    canonical_name: str


class CreateIngredientRequest(BaseModel):
    name: str

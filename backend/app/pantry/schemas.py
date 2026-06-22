"""Pydantic models for the pantry 'still have it?' API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PantryItemRead(BaseModel):
    item_id: int
    ingredient_id: int
    ingredient_name: str | None
    pantry_status: str
    last_qty: float | None = None
    last_unit: str | None = None
    purchased_at: datetime | None = None
    days_ago: int | None = None


class PantryView(BaseModel):
    items: list[PantryItemRead]


class PantryDecisionRequest(BaseModel):
    keep: bool

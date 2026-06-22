"""Pydantic models for the staples API."""

from __future__ import annotations

from pydantic import BaseModel


class StapleRead(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str | None
    auto_add: bool
    on_trip: bool


class StapleView(BaseModel):
    staples: list[StapleRead]


class AddStapleRequest(BaseModel):
    name: str


class AutoAddRequest(BaseModel):
    auto_add: bool

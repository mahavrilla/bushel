"""Pydantic request/response models for the matching + send API."""

from __future__ import annotations

from pydantic import BaseModel


class ProductChoice(BaseModel):
    upc: str
    description: str
    size: str | None = None
    price: float | None = None
    stock_level: str | None = None


class MatchItemRead(BaseModel):
    item_id: int
    ingredient_id: int
    ingredient_name: str | None
    total_qty: float | None
    total_unit: str | None
    purchase_qty: int
    purchase_qty_estimated: bool
    kroger_upc: str | None
    current: ProductChoice | None


class MatchRead(BaseModel):
    connected: bool
    store_location_id: str | None
    store_name: str | None = None
    items: list[MatchItemRead]


class SetStoreRequest(BaseModel):
    location_id: str
    name: str | None = None


class ConfirmRequest(BaseModel):
    kroger_upc: str
    kroger_description: str | None = None
    package_size: str | None = None


class SendRequest(BaseModel):
    modality: str = "PICKUP"


class SendItemResult(BaseModel):
    upc: str
    ok: bool
    error: str | None = None


class SendResult(BaseModel):
    status: str
    results: list[SendItemResult]

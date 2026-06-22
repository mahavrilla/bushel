"""Typed wrappers over the Kroger JSON we consume, plus API request/response models."""

from __future__ import annotations

from pydantic import BaseModel


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    scope: str = ""


class Location(BaseModel):
    location_id: str
    name: str
    address: str


class Product(BaseModel):
    upc: str
    description: str
    size: str | None = None
    price: float | None = None
    stock_level: str | None = None
    brand: str | None = None
    image_url: str | None = None


class KrogerStatus(BaseModel):
    connected: bool
    expired: bool


class LoginUrl(BaseModel):
    url: str

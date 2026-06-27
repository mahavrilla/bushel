"""Pure price math for multi-UPC comparison. No DB, no network. Prices are integer cents
except unit_price, which returns dollars-per-unit for display."""

from __future__ import annotations

from app.matching.purchase import parse_package_size


def to_cents(dollars: float | None) -> int | None:
    if dollars is None:
        return None
    return round(dollars * 100)


def effective_cents(regular_cents: int | None, promo_cents: int | None) -> int | None:
    """Promo wins only when present and strictly below regular (or regular is unknown)."""
    if promo_cents is not None and (regular_cents is None or promo_cents < regular_cents):
        return promo_cents
    return regular_cents


def is_on_sale(regular_cents: int | None, promo_cents: int | None) -> bool:
    return (
        regular_cents is not None
        and promo_cents is not None
        and promo_cents < regular_cents
    )


def unit_price(effective_cents: int | None, size_text: str | None) -> tuple[float, str] | None:
    """Dollars per unit, e.g. (0.17, 'fl oz'). None when there is no price or the package
    size cannot be parsed — never fabricate a unit price."""
    if effective_cents is None:
        return None
    parsed = parse_package_size(size_text)
    if parsed is None:
        return None
    qty, unit = parsed
    if qty <= 0:
        return None
    return (effective_cents / 100.0) / qty, unit

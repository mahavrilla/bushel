"""Pure consolidation of (qty, unit) pairs for one ingredient. The only pint importer.

Compatible units (by pint dimensionality) sum into the first-seen unit of their group;
units pint can't parse stay in their own group keyed by the unit string; count items
(unit is None) sum together; qty=None is carried through as an "as needed" marker.
"""

from __future__ import annotations

from pint import UnitRegistry

_ureg = UnitRegistry()

# Cooking aliases normalized BEFORE pint (pint reads bare 't'->tonne, 'l'->liter, etc.).
# Case-sensitive aliases checked FIRST (capital T = tablespoon, lowercase t = teaspoon).
_ALIASES_CASE_SENSITIVE = {
    "T": "tablespoon",
}

_ALIASES = {
    "tbsp": "tablespoon",
    "tbs": "tablespoon",
    "tb": "tablespoon",
    "t": "teaspoon",
    "tsp": "teaspoon",
    "c": "cup",
    "g": "gram",
    "kg": "kilogram",
    "ml": "milliliter",
    "l": "liter",
    "oz": "ounce",
    "lb": "pound",
    "lbs": "pound",
    "qt": "quart",
    "pt": "pint",
    "gal": "gallon",
}


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    raw = unit.strip()
    if not raw:
        return None
    # Case-sensitive first: capital "T" is tablespoon, lowercase "t" is teaspoon.
    if raw in _ALIASES_CASE_SENSITIVE:
        return _ALIASES_CASE_SENSITIVE[raw]
    key = raw.lower()
    # Collapse a trailing plural "s" so "cloves"->"clove", "cups"->"cup", "lbs"->"lb".
    if key.endswith("s") and not key.endswith("ss") and len(key) > 1:
        key = key[:-1]
    return _ALIASES.get(key, key)


def consolidate(items: list[tuple[float | None, str | None]]) -> list[dict]:
    """Return a list of {"qty": float|None, "unit": str|None} sub-quantities."""
    groups: list[dict] = []

    def find(key) -> dict | None:
        for g in groups:
            if g["key"] == key:
                return g
        return None

    for qty, raw_unit in items:
        unit = normalize_unit(raw_unit)

        if qty is None:
            key = ("none", unit)
            if find(key) is None:
                groups.append({"key": key, "unit": unit, "qty": None})
            continue

        if unit is None:
            key = ("count",)
            g = find(key)
            if g is None:
                groups.append({"key": key, "unit": None, "qty": qty})
            elif g["qty"] is not None:
                g["qty"] += qty
            continue

        try:
            q = qty * _ureg(unit)
            key = ("dim", str(q.dimensionality))
            g = find(key)
            if g is None:
                groups.append({"key": key, "unit": unit, "qty": qty})
            else:
                converted = q.to(g["unit"]).magnitude
                if g["qty"] is not None:
                    g["qty"] += converted
        except Exception:  # noqa: BLE001 — pint raises several types (UndefinedUnitError, DimensionalityError, ...) for non-units
            key = ("str", unit)
            g = find(key)
            if g is None:
                groups.append({"key": key, "unit": unit, "qty": qty})
            elif g["qty"] is not None:
                g["qty"] += qty

    return [
        {"qty": round(g["qty"], 3) if g["qty"] is not None else None, "unit": g["unit"]}
        for g in groups
    ]


def convert_qty(qty: float, from_unit: str | None, to_unit: str | None) -> float | None:
    """Convert qty from one unit to another. Returns None when units are missing,
    unparseable by pint, or dimensionally incompatible. Same normalized unit passes through."""
    fu = normalize_unit(from_unit)
    tu = normalize_unit(to_unit)
    if fu is None or tu is None:
        return None
    if fu == tu:
        return qty
    try:
        return (qty * _ureg(fu)).to(_ureg(tu)).magnitude
    except Exception:  # noqa: BLE001 — pint raises several types for non-units / bad conversions
        return None

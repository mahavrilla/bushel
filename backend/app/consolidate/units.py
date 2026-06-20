"""Pure consolidation of (qty, unit) pairs for one ingredient. The only pint importer.

Compatible units (by pint dimensionality) sum into the first-seen unit of their group;
units pint can't parse stay in their own group keyed by the unit string; count items
(unit is None) sum together; qty=None is carried through as an "as needed" marker.
"""

from __future__ import annotations

from pint import UndefinedUnitError, UnitRegistry

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


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    stripped = unit.strip()
    if not stripped:
        return None
    # Check case-sensitive aliases first (e.g. capital T = tablespoon).
    if stripped in _ALIASES_CASE_SENSITIVE:
        return _ALIASES_CASE_SENSITIVE[stripped]
    key = stripped.lower()
    base = key[:-1] if key.endswith("s") and key[:-1] in _ALIASES else key
    return _ALIASES.get(base, _ALIASES.get(key, base if base in _ALIASES else key))


def consolidate(items: list[tuple[float | None, str | None]]) -> list[dict]:
    """Return a list of {"qty": float|None, "unit": str|None} sub-quantities."""
    groups: list[dict] = []

    def find(key) -> dict | None:
        for g in groups:
            if g["key"] == key:
                return g
        return None

    for qty, raw_unit in items:
        unit = _normalize_unit(raw_unit)

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
        except (UndefinedUnitError, Exception):  # noqa: BLE001 — pint raises several types for bad units
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

"""Translate a consolidated total into a number of packages to buy.

No pint import here — unit math goes through consolidate.units.convert_qty so pint
stays isolated to one module.
"""

from __future__ import annotations

import math
import re

from app.consolidate.units import convert_qty

_PKG_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(.*?)\s*$")


def parse_package_size(text: str | None) -> tuple[float, str] | None:
    """Parse a Kroger package_size string like '5 lb' / '16.9 fl oz' / '6 ct'.

    Returns (qty, unit_text) or None when there is no leading number."""
    if not text:
        return None
    m = _PKG_RE.match(text)
    if not m:
        return None
    qty = float(m.group(1))
    unit = m.group(2).strip() or None
    if unit is None:
        return None
    return qty, unit


def compute_purchase_qty(
    total_qty: float | None, total_unit: str | None, package_size: str | None
) -> tuple[int, bool]:
    """Return (purchase_qty, estimated). estimated=True means we fell back to 1 because
    the total is unknown or units could not be reconciled — the UI should flag it."""
    if total_qty is None:
        return 1, True
    parsed = parse_package_size(package_size)
    if parsed is None:
        return 1, True
    pkg_qty, pkg_unit = parsed
    if pkg_qty <= 0:
        return 1, True
    converted = convert_qty(total_qty, total_unit, pkg_unit)
    if converted is None:
        return 1, True
    return max(math.ceil(converted / pkg_qty), 1), False

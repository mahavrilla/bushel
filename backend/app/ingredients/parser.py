"""Parse one raw ingredient line into {qty, unit, name}. Library-first, LLM fallback."""

from __future__ import annotations

from dataclasses import dataclass

from ingredient_parser import parse_ingredient

from app.llm.client import LLMClient, LLMUnavailableError

CONFIDENCE_THRESHOLD = 0.85


@dataclass(frozen=True)
class ParsedLine:
    qty: float | None
    unit: str | None
    name: str
    source: str  # "library" | "llm" | "library_low_confidence"


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _from_library(raw_text: str):
    """Map the library result to (name, qty, unit, confidence).

    ingredient_parser 2.7.0 shape:
    - parsed.name  → list[IngredientText]  each has .text (str) and .confidence (float)
    - parsed.amount → list[IngredientAmount] each has:
        .quantity  (fractions.Fraction or None)
        .unit      (pint.Unit *or* plain str, or None when absent)
        .confidence (float)

    We take the first element of each list (highest-confidence entry) and derive a
    combined confidence = min(name_conf, amount_conf).  When no amount is present we
    use name_conf alone (un-quantified lines such as "salt to taste").
    """
    parsed = parse_ingredient(raw_text)

    name_obj = parsed.name[0] if parsed.name else None
    amount_list = getattr(parsed, "amount", None) or []
    amount_obj = amount_list[0] if amount_list else None

    name = name_obj.text if name_obj else raw_text
    name_conf = float(getattr(name_obj, "confidence", 0.0)) if name_obj else 0.0

    qty = _to_float(getattr(amount_obj, "quantity", None)) if amount_obj else None
    # unit may be a pint.Unit (str() → "cup") or a plain str ("pinch") or None
    raw_unit = getattr(amount_obj, "unit", None) if amount_obj else None
    unit = str(raw_unit) if raw_unit is not None else None
    amount_conf = float(getattr(amount_obj, "confidence", 0.0)) if amount_obj else 0.0

    confidence = min(name_conf, amount_conf) if amount_obj else name_conf
    return name, qty, unit, confidence


def parse_line(raw_text: str, llm: LLMClient) -> ParsedLine:
    name, qty, unit, confidence = _from_library(raw_text)
    if confidence >= CONFIDENCE_THRESHOLD:
        return ParsedLine(qty=qty, unit=unit, name=name, source="library")
    try:
        llm_result = llm.parse_ingredient_line(raw_text)
    except LLMUnavailableError:
        return ParsedLine(qty=qty, unit=unit, name=name, source="library_low_confidence")
    return ParsedLine(qty=llm_result.qty, unit=llm_result.unit, name=llm_result.name, source="llm")

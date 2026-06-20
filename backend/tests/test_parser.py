"""Tests for app/ingredients/parser.py — mocked library + one real sanity check."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fractions import Fraction

from app.ingredients.parser import ParsedLine, parse_line
from app.llm.client import LLMUnavailableError, ParsedLineLLM


def _lib_result(name, name_conf, qty, unit, amount_conf):
    """Mimic ingredient_parser 2.7.0's parse_ingredient return shape.

    - name  → list of SimpleNamespace(text=..., confidence=...)
    - amount → list of SimpleNamespace(quantity=Fraction|None, unit=str|pint.Unit|None,
                                        confidence=float)
    Quantity is a Fraction (or None); unit is a string (or None when absent).
    """
    amount_ns = SimpleNamespace(
        quantity=Fraction(qty) if qty is not None else None,
        unit=unit,
        confidence=amount_conf,
    )
    return SimpleNamespace(
        name=[SimpleNamespace(text=name, confidence=name_conf)],
        amount=[amount_ns] if qty is not None or unit is not None else [],
    )


@patch("app.ingredients.parser.parse_ingredient")
def test_high_confidence_uses_library(mock_parse):
    mock_parse.return_value = _lib_result("all-purpose flour", 0.97, "2", "cup", 0.96)
    llm = MagicMock()
    result = parse_line("2 cups all-purpose flour", llm)
    assert result == ParsedLine(qty=2.0, unit="cup", name="all-purpose flour", source="library")
    llm.parse_ingredient_line.assert_not_called()


@patch("app.ingredients.parser.parse_ingredient")
def test_low_confidence_falls_back_to_llm(mock_parse):
    mock_parse.return_value = _lib_result("stuff", 0.20, None, None, 0.10)
    llm = MagicMock()
    llm.parse_ingredient_line.return_value = ParsedLineLLM(qty=1.0, unit="pinch", name="saffron")
    result = parse_line("a pinch of saffron threads", llm)
    assert result == ParsedLine(qty=1.0, unit="pinch", name="saffron", source="llm")
    llm.parse_ingredient_line.assert_called_once()


@patch("app.ingredients.parser.parse_ingredient")
def test_llm_unavailable_returns_unparsed_library_result(mock_parse):
    mock_parse.return_value = _lib_result("saffron", 0.30, None, None, 0.10)
    llm = MagicMock()
    llm.parse_ingredient_line.side_effect = LLMUnavailableError("no key")
    result = parse_line("a pinch of saffron threads", llm)
    assert result.name == "saffron"
    assert result.source == "library_low_confidence"


def test_real_library_parses_common_line():
    """Exercises the real ingredient_parser (no mock) to keep the adapter honest."""
    from app.ingredients.parser import _from_library

    name, qty, unit, confidence = _from_library("2 cups all-purpose flour")
    assert "flour" in name.lower()
    assert qty == 2.0
    assert confidence > 0.0

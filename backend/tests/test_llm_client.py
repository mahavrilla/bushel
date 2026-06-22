from unittest.mock import MagicMock, patch

import pytest

from app.llm.client import (
    LLMClient,
    LLMUnavailableError,
    ParsedLineLLM,
    CanonicalizeOne,
    CanonicalizeResult,
    NewIngredientLLM,
    ScrapedRecipeLLM,
    ExtractedIngredientsLLM,
)


def test_unavailable_when_no_api_key():
    client = LLMClient(api_key="")
    with pytest.raises(LLMUnavailableError):
        client.parse_ingredient_line("2 cups flour")


@patch("app.llm.client.anthropic.Anthropic")
def test_parse_ingredient_line_returns_structured(mock_anthropic):
    parsed = ParsedLineLLM(qty=2.0, unit="cup", name="all-purpose flour")
    mock_response = MagicMock(stop_reason="end_turn", parsed_output=parsed)
    mock_anthropic.return_value.messages.parse.return_value = mock_response

    client = LLMClient(api_key="sk-test")
    result = client.parse_ingredient_line("2 cups all-purpose flour")

    assert result.qty == 2.0
    assert result.unit == "cup"
    assert result.name == "all-purpose flour"
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    assert kwargs["model"] == "claude-haiku-4-5"


@patch("app.llm.client.anthropic.Anthropic")
def test_refusal_raises_unavailable(mock_anthropic):
    mock_response = MagicMock(stop_reason="refusal", parsed_output=None)
    mock_anthropic.return_value.messages.parse.return_value = mock_response

    client = LLMClient(api_key="sk-test")
    with pytest.raises(LLMUnavailableError):
        client.parse_ingredient_line("2 cups flour")


@patch("app.llm.client.anthropic.Anthropic")
def test_canonicalize_builds_prompt_and_returns_result(mock_anthropic):
    expected = CanonicalizeResult(
        results=[
            CanonicalizeOne(
                query="saffron",
                new=NewIngredientLLM(
                    canonical_name="saffron", category="spice", default_purchase_unit="jar"
                ),
            )
        ]
    )
    mock_anthropic.return_value.messages.parse.return_value = MagicMock(
        stop_reason="end_turn", parsed_output=expected
    )

    client = LLMClient(api_key="sk-test")
    result = client.canonicalize_ingredients(
        ["saffron"], existing=[{"id": 42, "canonical_name": "all purpose flour"}]
    )

    assert result.results[0].new.canonical_name == "saffron"
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    # the existing set and the query both appear in the prompt
    assert "id=42" in kwargs["messages"][0]["content"]
    assert "saffron" in kwargs["messages"][0]["content"]


@patch("app.llm.client.anthropic.Anthropic")
def test_scrape_recipe_truncates_html(mock_anthropic):
    expected = ScrapedRecipeLLM(title="Bread", servings=2, raw_lines=["3 cups flour"])
    mock_anthropic.return_value.messages.parse.return_value = MagicMock(
        stop_reason="end_turn", parsed_output=expected
    )

    client = LLMClient(api_key="sk-test")
    long_html = "x" * 70000
    result = client.scrape_recipe(long_html, "https://example.com/bread")

    assert result.title == "Bread"
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    # HTML is truncated to 60000 chars in the prompt
    assert "x" * 60000 in kwargs["messages"][0]["content"]
    assert "x" * 60001 not in kwargs["messages"][0]["content"]


@patch("app.llm.client.anthropic.Anthropic")
def test_extract_ingredients_returns_lines(mock_anthropic):
    expected = ExtractedIngredientsLLM(lines=["ground turkey", "olive oil"])
    mock_anthropic.return_value.messages.parse.return_value = MagicMock(
        stop_reason="end_turn", parsed_output=expected
    )
    client = LLMClient(api_key="sk-test")
    result = client.extract_ingredients("Ingredients\n- Ground turkey\n- Olive oil\nSteps\n1. cook")
    assert result == ["ground turkey", "olive oil"]
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    assert kwargs["model"] == "claude-haiku-4-5"

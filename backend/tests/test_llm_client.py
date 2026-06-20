from unittest.mock import MagicMock, patch

import pytest

from app.llm.client import (
    LLMClient,
    LLMUnavailableError,
    ParsedLineLLM,
    CanonicalizeResult,
    ScrapedRecipeLLM,
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

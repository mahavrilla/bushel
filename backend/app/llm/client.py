"""The single Anthropic integration point. Structured extraction via Claude Haiku 4.5."""

from __future__ import annotations

import anthropic
from pydantic import BaseModel

from app.config import get_settings

MODEL = "claude-haiku-4-5"


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM cannot be used (no key, API error, or refusal)."""


class ParsedLineLLM(BaseModel):
    qty: float | None = None
    unit: str | None = None
    name: str


class NewIngredientLLM(BaseModel):
    canonical_name: str
    category: str | None = None
    default_purchase_unit: str | None = None


class CanonicalizeOne(BaseModel):
    """For one unknown ingredient: either alias an existing id, or a new ingredient."""

    query: str
    alias_of: int | None = None
    new: NewIngredientLLM | None = None


class CanonicalizeResult(BaseModel):
    results: list[CanonicalizeOne]


class ScrapedRecipeLLM(BaseModel):
    title: str
    servings: int | None = None
    raw_lines: list[str]


class LLMClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else get_settings().anthropic_api_key
        self._client: anthropic.Anthropic | None = None

    def _ensure(self) -> anthropic.Anthropic:
        if not self._api_key:
            raise LLMUnavailableError("ANTHROPIC_API_KEY is not set")
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _parse(self, *, system: str, user: str, output_format: type[BaseModel], max_tokens: int):
        client = self._ensure()
        try:
            resp = client.messages.parse(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output_format,
            )
        except anthropic.APIError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            raise LLMUnavailableError("LLM refused or returned no structured output")
        return resp.parsed_output

    def parse_ingredient_line(self, raw_text: str) -> ParsedLineLLM:
        return self._parse(
            system=(
                "You parse a single recipe ingredient line into structured data. "
                "Extract the numeric quantity, the unit (singular, lowercase, e.g. 'cup', "
                "'tablespoon', 'gram', 'clove'), and the ingredient name (without quantity, "
                "unit, or prep notes). If there is no quantity or unit, leave it null."
            ),
            user=raw_text,
            output_format=ParsedLineLLM,
            max_tokens=512,
        )

    def canonicalize_ingredients(
        self, queries: list[str], existing: list[dict]
    ) -> CanonicalizeResult:
        """Classify each unknown ingredient against the existing canonical set."""
        existing_str = "\n".join(f"- id={e['id']}: {e['canonical_name']}" for e in existing)
        return self._parse(
            system=(
                "You match unknown grocery ingredients to a canonical list, or mark them new. "
                "For each query: if it means the same grocery item as an existing entry, set "
                "alias_of to that id. Otherwise set new with a canonical_name (lowercase, "
                "singular), a category (one of: produce, meat, dairy, baking, pantry, frozen, "
                "beverage, spice, other), and a default_purchase_unit describing how you buy it "
                "(e.g. 'bag', 'dozen', 'lb', 'bunch', 'can', 'bottle'). Return one result per "
                "query, echoing the query string."
            ),
            user=f"EXISTING:\n{existing_str or '(none)'}\n\nQUERIES:\n"
            + "\n".join(queries),
            output_format=CanonicalizeResult,
            max_tokens=2048,
        )

    def scrape_recipe(self, html: str, url: str) -> ScrapedRecipeLLM:
        return self._parse(
            system=(
                "Extract a recipe from this HTML. Return the title, the number of servings "
                "(integer, or null), and raw_lines: the ingredient lines exactly as written, "
                "one string per ingredient. Ignore instructions, ads, and comments."
            ),
            user=f"URL: {url}\n\nHTML:\n{html[:60000]}",
            output_format=ScrapedRecipeLLM,
            max_tokens=4096,
        )

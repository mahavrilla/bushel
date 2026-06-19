# Bushel Phase 2 — Recipes & Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the recipe-import and ingredient-parsing subsystem — import recipes by URL (recipe-scrapers + Claude fallback) or manual entry, parse ingredient lines (ingredient-parser + Claude fallback), resolve them to canonical deduplicated ingredients (normalize + alias, Claude only for new), flag low-confidence results for review, and expose it through an API and three React screens.

**Architecture:** Builds on the completed Phase 1 foundation (FastAPI + Postgres + React, full 8-table schema). Adds four backend modules — `recipes/`, `ingredients/`, `llm/` — plus the first real API router. Fuzzy logic (scraping, ML parsing, Claude) is isolated behind small interfaces so the deterministic core (string normalization, DB writes) and everything else can be unit-tested with the LLM and libraries mocked. One additive migration adds `needs_review` to `recipe_ingredients`. Import is synchronous.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / uv; `recipe-scrapers`, `ingredient-parser-nlp`, `anthropic` (Claude Haiku 4.5, model id `claude-haiku-4-5`); React 18 / TypeScript / Vite / Vitest. `pint` is pulled in transitively by `ingredient-parser-nlp` but unit conversion is Phase 3, not used here.

---

## Important context for the implementer

- **The Phase 1 schema already exists.** `app/models.py` has `Recipe`, `RecipeIngredient` (`raw_text`, `qty`, `unit`, `ingredient_id`, `parse_source`), and `Ingredient` (`canonical_name` unique, `aliases` text[], `category`, `default_purchase_unit`). This phase only *populates* them and adds one column.
- **`app/db.py`** provides `Base`, `engine`, `SessionLocal`, `get_db`. **`app/config.py`** provides `get_settings()` with `anthropic_api_key`. **`app/main.py`** is the FastAPI app (`/health` only; no routers yet).
- **Tests** use the `db_session` fixture from `tests/conftest.py` (transaction rolled back per test) and a configured Postgres test DB (`export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5432/bushel_test`, with `bushel-pg` running). Run with `uv run pytest` from `backend/`.
- **The LLM is mocked in every automated test.** No test makes a real Anthropic call.
- **External-library adapters (`scraper.py`, `parser.py`) are version-sensitive.** Each relevant task says to *verify the installed library's actual API and adjust the thin adapter accordingly* — this is expected work for wrapping a third-party dependency, not a plan defect. The adapter's job is to map the library's output to our own value object; our tests assert against our value object.

## File Structure

```
backend/
├── pyproject.toml                 # + recipe-scrapers, ingredient-parser-nlp, anthropic
├── migrations/versions/<rev>_add_needs_review.py   # new migration
├── app/
│   ├── main.py                    # MODIFY: include recipes router
│   ├── models.py                  # MODIFY: add needs_review to RecipeIngredient
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py              # Claude wrapper: parse_ingredient_line, canonicalize_ingredients, scrape_recipe
│   ├── ingredients/
│   │   ├── __init__.py
│   │   ├── normalize.py           # pure string normalization
│   │   ├── parser.py              # ingredient-parser wrapper + LLM fallback → ParsedLine
│   │   └── canonicalize.py        # normalize + alias lookup; batched LLM for misses
│   └── recipes/
│       ├── __init__.py
│       ├── schemas.py             # Pydantic request/response models
│       ├── scraper.py             # recipe-scrapers wrapper + LLM fallback → ScrapedRecipe
│       ├── service.py             # orchestrator: scrape → parse → canonicalize → persist
│       └── router.py              # FastAPI endpoints
│   └── tests/                     # (under backend/tests/, mirrors app/)
└── tests/
    ├── test_normalize.py
    ├── test_llm_client.py
    ├── test_parser.py
    ├── test_canonicalize.py
    ├── test_scraper.py
    ├── test_recipe_service.py
    ├── test_recipes_router.py
    └── fixtures/                  # saved recipe HTML
frontend/
└── src/
    ├── api.ts                     # MODIFY: + recipe endpoints + types
    ├── App.tsx                    # MODIFY: simple nav between screens
    ├── recipes/
    │   ├── types.ts               # shared TS types
    │   ├── AddRecipe.tsx
    │   ├── AddRecipe.test.tsx
    │   ├── RecipeDetail.tsx
    │   ├── RecipeDetail.test.tsx
    │   ├── RecipeList.tsx
    │   └── RecipeList.test.tsx
```

**Responsibilities:** `llm/client.py` is the only file that imports `anthropic`. `normalize.py` is pure/dependency-free. `parser.py` and `scraper.py` are the only files importing `ingredient_parser` and `recipe_scrapers` respectively. `service.py` is the only place that writes `Recipe`/`RecipeIngredient` rows. `router.py` is thin HTTP. `api.ts` is the only frontend module that knows endpoint URLs.

---

## Task 1: Add dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add the three runtime dependencies** to `backend/pyproject.toml` `[project].dependencies` (keep existing entries):

```toml
    "recipe-scrapers>=15.0",
    "ingredient-parser-nlp>=1.1",
    "anthropic>=0.40",
```

- [ ] **Step 2: Resolve and lock**

Run (from `backend/`): `uv lock && uv sync`
Expected: lockfile updates; all three packages resolve and install. `ingredient-parser-nlp` downloads its model on first parse (network needed once).

- [ ] **Step 3: Verify imports work**

Run (from `backend/`): `uv run python -c "import recipe_scrapers, ingredient_parser, anthropic; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "build(backend): add recipe-scrapers, ingredient-parser, anthropic deps"
```

---

## Task 2: Add `needs_review` column + migration

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_models.py` (append)
- Create: migration under `backend/migrations/versions/`

- [ ] **Step 1: Append a failing test** to `backend/tests/test_models.py`:

```python
def test_recipe_ingredient_has_needs_review():
    from app.models import RecipeIngredient

    cols = RecipeIngredient.__table__.columns
    assert "needs_review" in cols
    assert cols["needs_review"].default.arg is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_models.py::test_recipe_ingredient_has_needs_review -v`
Expected: FAIL — `needs_review` not in columns.

- [ ] **Step 3: Add the column** to the `RecipeIngredient` class in `backend/app/models.py` (after `parse_source`):

```python
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
```

`Boolean` is already imported in `models.py` (used by `IngredientProductMap.is_default`).

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_models.py::test_recipe_ingredient_has_needs_review -v`
Expected: PASS.

- [ ] **Step 5: Generate the migration**

Ensure `DATABASE_URL` points at a database already at Phase 1 `head` (run `uv run alembic upgrade head` first if needed).
Run (from `backend/`): `uv run alembic revision --autogenerate -m "add needs_review to recipe_ingredients"`
Expected: a new versions file whose `upgrade()` calls `op.add_column("recipe_ingredients", sa.Column("needs_review", ...))`. Open it and confirm it adds exactly that one column (no unrelated drift). If it includes unrelated changes, the DB wasn't at head — fix and regenerate.

- [ ] **Step 6: Apply and verify round-trip**

Run: `uv run alembic upgrade head` then `uv run alembic downgrade -1` then `uv run alembic upgrade head`
Expected: all succeed.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py backend/migrations/versions
git commit -m "feat(backend): add needs_review column to recipe_ingredients"
```

---

## Task 3: `ingredients/normalize.py` (pure)

**Files:**
- Create: `backend/app/ingredients/__init__.py` (empty)
- Create: `backend/app/ingredients/normalize.py`
- Test: `backend/tests/test_normalize.py`

- [ ] **Step 1: Create the empty package marker** `backend/app/ingredients/__init__.py` (empty file).

- [ ] **Step 2: Write the failing test** `backend/tests/test_normalize.py`:

```python
import pytest

from app.ingredients.normalize import normalize_name


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("All-Purpose Flour", "all purpose flour"),
        ("  AP   Flour ", "ap flour"),
        ("Eggs", "egg"),
        ("Tomatoes", "tomato"),
        ("Cherry Tomatoes", "cherry tomato"),
        ("olive oil,", "olive oil"),
        ("Boneless Chicken Breasts", "boneless chicken breast"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_normalize.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement** `backend/app/ingredients/normalize.py`:

```python
"""Pure, dependency-free normalization of ingredient names for dedup lookups."""

import re

_PUNCT = re.compile(r"[^a-z0-9\s]")
_WS = re.compile(r"\s+")


def _singularize(word: str) -> str:
    """Crude English singularizer — enough for ingredient names."""
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("ses") or word.endswith("xes") or word.endswith("zes"):
        return word[:-2]
    if word.endswith("oes") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def normalize_name(raw: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, singularize each word."""
    text = raw.lower()
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return " ".join(_singularize(w) for w in text.split())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_normalize.py -v`
Expected: PASS (all 7 cases).

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingredients/__init__.py backend/app/ingredients/normalize.py backend/tests/test_normalize.py
git commit -m "feat(backend): add pure ingredient name normalization"
```

---

## Task 4: `llm/client.py` — Claude wrapper

Defines our LLM interface and the Pydantic shapes the rest of the app consumes. Uses `client.messages.parse(..., output_format=Model)` for validated structured extraction with Claude Haiku 4.5.

**Files:**
- Create: `backend/app/llm/__init__.py` (empty)
- Create: `backend/app/llm/client.py`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Create the empty package marker** `backend/app/llm/__init__.py`.

- [ ] **Step 2: Write the failing test** `backend/tests/test_llm_client.py` (the Anthropic client is mocked — no network):

```python
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
    # used the configured model
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    assert kwargs["model"] == "claude-haiku-4-5"


@patch("app.llm.client.anthropic.Anthropic")
def test_refusal_raises_unavailable(mock_anthropic):
    mock_response = MagicMock(stop_reason="refusal", parsed_output=None)
    mock_anthropic.return_value.messages.parse.return_value = mock_response

    client = LLMClient(api_key="sk-test")
    with pytest.raises(LLMUnavailableError):
        client.parse_ingredient_line("2 cups flour")
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement** `backend/app/llm/client.py`:

```python
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
        except anthropic.APIError as exc:  # rate limit, server error, connection, etc.
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm backend/tests/test_llm_client.py
git commit -m "feat(backend): add Claude LLM client for structured extraction"
```

---

## Task 5: `ingredients/parser.py` — library-first, LLM fallback

**Files:**
- Create: `backend/app/ingredients/parser.py`
- Test: `backend/tests/test_parser.py`

> **Adapter note:** `ingredient_parser.parse_ingredient(text)` returns a `ParsedIngredient`. Field shapes vary by version — typically `.name` is a list of objects with `.text`/`.confidence`, and `.amount` is a list of objects with `.quantity`/`.unit`/`.confidence`. **Verify against the installed version** (`uv run python -c "from ingredient_parser import parse_ingredient; p=parse_ingredient('2 cups flour'); print(p)"`) and adjust `_from_library` accordingly. Our tests mock `parse_ingredient`, so they assert our `ParsedLine` shape regardless of the library's internal types.

- [ ] **Step 1: Write the failing test** `backend/tests/test_parser.py`:

```python
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ingredients.parser import ParsedLine, parse_line
from app.llm.client import LLMUnavailableError, ParsedLineLLM

CONF_THRESHOLD = 0.85


def _lib_result(name, name_conf, qty, unit, amount_conf):
    """Shape mimicking ingredient_parser's ParsedIngredient (adjust to installed version)."""
    return SimpleNamespace(
        name=[SimpleNamespace(text=name, confidence=name_conf)],
        amount=[SimpleNamespace(quantity=qty, unit=unit, confidence=amount_conf)],
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

    # Degrades to whatever the library gave, flagged low-confidence via source
    assert result.name == "saffron"
    assert result.source == "library_low_confidence"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_parser.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `backend/app/ingredients/parser.py`:

```python
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
    """Map the library result to (name, qty, unit, confidence). Adjust to installed API."""
    parsed = parse_ingredient(raw_text)
    name_obj = parsed.name[0] if parsed.name else None
    amount_obj = parsed.amount[0] if getattr(parsed, "amount", None) else None
    name = name_obj.text if name_obj else raw_text
    name_conf = float(getattr(name_obj, "confidence", 0.0)) if name_obj else 0.0
    qty = _to_float(getattr(amount_obj, "quantity", None)) if amount_obj else None
    unit = str(amount_obj.unit) if amount_obj and amount_obj.unit else None
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
    return ParsedLine(
        qty=llm_result.qty, unit=llm_result.unit, name=llm_result.name, source="llm"
    )
```

- [ ] **Step 4: Verify the library adapter against the installed version**

Run: `uv run python -c "from ingredient_parser import parse_ingredient; p=parse_ingredient('2 cups all-purpose flour'); print(repr(p.name)); print(repr(p.amount))"`
Inspect the printed structure. If `.name` / `.amount` field names or nesting differ from the test's `SimpleNamespace` mock, update **both** `_from_library` and the `_lib_result` helper in the test to match the real shape (keep the same `ParsedLine` assertions).

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_parser.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingredients/parser.py backend/tests/test_parser.py
git commit -m "feat(backend): add ingredient line parser with LLM fallback"
```

---

## Task 6: `ingredients/canonicalize.py`

**Files:**
- Create: `backend/app/ingredients/canonicalize.py`
- Test: `backend/tests/test_canonicalize.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_canonicalize.py` (uses `db_session`; LLM mocked):

```python
from unittest.mock import MagicMock

from app.ingredients.canonicalize import CanonResult, canonicalize_names
from app.llm.client import (
    CanonicalizeOne,
    CanonicalizeResult,
    LLMUnavailableError,
    NewIngredientLLM,
)
from app.models import Ingredient


def test_exact_normalized_hit_reuses_existing(db_session):
    existing = Ingredient(canonical_name="all purpose flour", aliases=[])
    db_session.add(existing)
    db_session.flush()
    llm = MagicMock()

    results = canonicalize_names(["All-Purpose Flour"], db_session, llm)

    assert results["All-Purpose Flour"] == CanonResult(ingredient_id=existing.id, is_new=False)
    llm.canonicalize_ingredients.assert_not_called()


def test_alias_hit_reuses_existing(db_session):
    existing = Ingredient(canonical_name="all purpose flour", aliases=["ap flour"])
    db_session.add(existing)
    db_session.flush()
    llm = MagicMock()

    results = canonicalize_names(["AP Flour"], db_session, llm)

    assert results["AP Flour"].ingredient_id == existing.id
    assert results["AP Flour"].is_new is False
    llm.canonicalize_ingredients.assert_not_called()


def test_miss_creates_new_with_metadata(db_session):
    llm = MagicMock()
    llm.canonicalize_ingredients.return_value = CanonicalizeResult(
        results=[
            CanonicalizeOne(
                query="saffron",
                new=NewIngredientLLM(
                    canonical_name="saffron", category="spice", default_purchase_unit="jar"
                ),
            )
        ]
    )

    results = canonicalize_names(["saffron"], db_session, llm)

    new_id = results["saffron"].ingredient_id
    assert results["saffron"].is_new is True
    created = db_session.get(Ingredient, new_id)
    assert created.canonical_name == "saffron"
    assert created.category == "spice"
    assert created.default_purchase_unit == "jar"


def test_miss_alias_of_existing_adds_alias(db_session):
    existing = Ingredient(canonical_name="all purpose flour", aliases=[])
    db_session.add(existing)
    db_session.flush()
    llm = MagicMock()
    llm.canonicalize_ingredients.return_value = CanonicalizeResult(
        results=[CanonicalizeOne(query="plain flour", alias_of=existing.id)]
    )

    results = canonicalize_names(["plain flour"], db_session, llm)

    assert results["plain flour"].ingredient_id == existing.id
    assert results["plain flour"].is_new is False
    db_session.refresh(existing)
    assert "plain flour" in existing.aliases


def test_llm_unavailable_creates_new_flagged(db_session):
    llm = MagicMock()
    llm.canonicalize_ingredients.side_effect = LLMUnavailableError("no key")

    results = canonicalize_names(["dragonfruit"], db_session, llm)

    assert results["dragonfruit"].is_new is True
    created = db_session.get(Ingredient, results["dragonfruit"].ingredient_id)
    assert created.canonical_name == "dragonfruit"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_canonicalize.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `backend/app/ingredients/canonicalize.py`:

```python
"""Resolve parsed ingredient names to canonical Ingredient rows.

Deterministic for known ingredients (normalized name + alias lookup); the LLM is
consulted once, batched, only for names with no local match.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingredients.normalize import normalize_name
from app.llm.client import LLMClient, LLMUnavailableError
from app.models import Ingredient


@dataclass(frozen=True)
class CanonResult:
    ingredient_id: int
    is_new: bool


def _lookup(normalized: str, ingredients: list[Ingredient]) -> Ingredient | None:
    for ing in ingredients:
        if ing.canonical_name == normalized:
            return ing
        if normalized in (ing.aliases or []):
            return ing
    return None


def _create_new(db: Session, canonical_name: str, category=None, purchase_unit=None) -> Ingredient:
    ing = Ingredient(
        canonical_name=canonical_name,
        aliases=[],
        category=category,
        default_purchase_unit=purchase_unit,
    )
    db.add(ing)
    db.flush()
    return ing


def canonicalize_names(
    queries: list[str], db: Session, llm: LLMClient
) -> dict[str, CanonResult]:
    ingredients = list(db.execute(select(Ingredient)).scalars())
    results: dict[str, CanonResult] = {}
    misses: list[str] = []
    miss_normalized: dict[str, str] = {}

    for q in queries:
        normalized = normalize_name(q)
        hit = _lookup(normalized, ingredients)
        if hit is not None:
            results[q] = CanonResult(ingredient_id=hit.id, is_new=False)
        else:
            misses.append(q)
            miss_normalized[q] = normalized

    if not misses:
        return results

    existing_payload = [{"id": i.id, "canonical_name": i.canonical_name} for i in ingredients]
    try:
        classified = llm.canonicalize_ingredients(misses, existing_payload)
        by_query = {c.query: c for c in classified.results}
    except LLMUnavailableError:
        by_query = {}

    for q in misses:
        decision = by_query.get(q)
        if decision is not None and decision.alias_of is not None:
            existing = db.get(Ingredient, decision.alias_of)
            if existing is not None:
                normalized = miss_normalized[q]
                if normalized not in (existing.aliases or []):
                    existing.aliases = [*(existing.aliases or []), normalized]
                results[q] = CanonResult(ingredient_id=existing.id, is_new=False)
                continue
        if decision is not None and decision.new is not None:
            created = _create_new(
                db,
                normalize_name(decision.new.canonical_name),
                decision.new.category,
                decision.new.default_purchase_unit,
            )
        else:
            # LLM unavailable or ambiguous → create new from the normalized name, flagged by caller
            created = _create_new(db, miss_normalized[q])
        results[q] = CanonResult(ingredient_id=created.id, is_new=True)

    return results
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_canonicalize.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingredients/canonicalize.py backend/tests/test_canonicalize.py
git commit -m "feat(backend): add ingredient canonicalization with batched LLM fallback"
```

---

## Task 7: `recipes/scraper.py`

**Files:**
- Create: `backend/app/recipes/__init__.py` (empty)
- Create: `backend/app/recipes/scraper.py`
- Test: `backend/tests/test_scraper.py`

> **Adapter note:** Use `recipe_scrapers.scrape_html(html, org_url=url)`. Unsupported sites raise an exception (historically `WebsiteNotImplementedError`; newer versions may use `NoSchemaFoundInWildMode` or similar). **Verify the installed version's import path and exception name** (`uv run python -c "import recipe_scrapers; print(dir(recipe_scrapers))"`) and adjust the import + `except` clause. Our tests patch `scrape_html`, so they don't depend on the exception's exact type beyond what we catch.

- [ ] **Step 1: Create the empty package marker** `backend/app/recipes/__init__.py`.

- [ ] **Step 2: Write the failing test** `backend/tests/test_scraper.py`:

```python
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.recipes.scraper import ScrapedRecipe, ScrapeError, scrape_url
from app.llm.client import LLMUnavailableError, ScrapedRecipeLLM


def _scraper(title, yields, ingredients):
    s = SimpleNamespace()
    s.title = lambda: title
    s.yields = lambda: yields
    s.ingredients = lambda: ingredients
    return s


@patch("app.recipes.scraper._fetch_html", return_value="<html>ok</html>")
@patch("app.recipes.scraper.scrape_html")
def test_library_scrape_success(mock_scrape, _fetch):
    mock_scrape.return_value = _scraper("Pancakes", "4 servings", ["2 cups flour", "1 egg"])
    llm = MagicMock()

    result = scrape_url("https://example.com/pancakes", llm)

    assert result == ScrapedRecipe(
        title="Pancakes", servings=4, raw_lines=["2 cups flour", "1 egg"]
    )
    llm.scrape_recipe.assert_not_called()


@patch("app.recipes.scraper._fetch_html", return_value="<html>ok</html>")
@patch("app.recipes.scraper.scrape_html", side_effect=Exception("unsupported site"))
def test_unsupported_site_falls_back_to_llm(mock_scrape, _fetch):
    llm = MagicMock()
    llm.scrape_recipe.return_value = ScrapedRecipeLLM(
        title="Bread", servings=2, raw_lines=["3 cups flour"]
    )

    result = scrape_url("https://blog.example/bread", llm)

    assert result == ScrapedRecipe(title="Bread", servings=2, raw_lines=["3 cups flour"])
    llm.scrape_recipe.assert_called_once()


@patch("app.recipes.scraper._fetch_html", return_value="<html>ok</html>")
@patch("app.recipes.scraper.scrape_html", side_effect=Exception("unsupported"))
def test_unsupported_and_llm_unavailable_raises(mock_scrape, _fetch):
    llm = MagicMock()
    llm.scrape_recipe.side_effect = LLMUnavailableError("no key")

    try:
        scrape_url("https://blog.example/bread", llm)
        assert False, "expected ScrapeError"
    except ScrapeError:
        pass
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_scraper.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement** `backend/app/recipes/scraper.py`:

```python
"""Scrape a recipe URL into {title, servings, raw_lines}. Library-first, LLM fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from recipe_scrapers import scrape_html

from app.llm.client import LLMClient, LLMUnavailableError

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BushelBot/1.0)"}
_DIGITS = re.compile(r"\d+")


class ScrapeError(RuntimeError):
    """Raised when neither the library nor the LLM could produce a usable recipe."""


@dataclass(frozen=True)
class ScrapedRecipe:
    title: str
    servings: int | None
    raw_lines: list[str]


def _fetch_html(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _yields_to_int(yields: str | None) -> int | None:
    if not yields:
        return None
    m = _DIGITS.search(yields)
    return int(m.group()) if m else None


def scrape_url(url: str, llm: LLMClient) -> ScrapedRecipe:
    try:
        html = _fetch_html(url)
    except requests.RequestException as exc:
        raise ScrapeError(f"could not fetch URL: {exc}") from exc

    try:
        scraper = scrape_html(html, org_url=url)
        lines = [line.strip() for line in scraper.ingredients() if line.strip()]
        if lines:
            return ScrapedRecipe(
                title=scraper.title() or url,
                servings=_yields_to_int(scraper.yields()),
                raw_lines=lines,
            )
    except Exception:  # noqa: BLE001 — library raises various site-specific errors
        pass

    try:
        llm_result = llm.scrape_recipe(html, url)
    except LLMUnavailableError as exc:
        raise ScrapeError("site unsupported and LLM unavailable") from exc

    lines = [line.strip() for line in llm_result.raw_lines if line.strip()]
    if not lines:
        raise ScrapeError("no ingredients found")
    return ScrapedRecipe(title=llm_result.title or url, servings=llm_result.servings, raw_lines=lines)
```

- [ ] **Step 5: Verify the library against the installed version**

Run: `uv run python -c "import recipe_scrapers; print([n for n in dir(recipe_scrapers) if 'scrape' in n.lower()])"`
Confirm `scrape_html` exists. If the import name differs, update the `from recipe_scrapers import ...` line. (The broad `except Exception` already tolerates whatever unsupported-site error the version raises.)

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_scraper.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/recipes/__init__.py backend/app/recipes/scraper.py backend/tests/test_scraper.py
git commit -m "feat(backend): add recipe URL scraper with LLM fallback"
```

---

## Task 8: `recipes/schemas.py` — Pydantic request/response models

**Files:**
- Create: `backend/app/recipes/schemas.py`
- Test: `backend/tests/test_recipe_schemas.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_recipe_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.recipes.schemas import ImportRequest, ManualRecipeRequest, IngredientUpdate


def test_import_request_requires_url():
    assert ImportRequest(url="https://example.com").url == "https://example.com"
    with pytest.raises(ValidationError):
        ImportRequest()


def test_manual_request_rejects_blank_title():
    with pytest.raises(ValidationError):
        ManualRecipeRequest(title="  ", servings=2, raw_lines=["1 egg"])


def test_manual_request_drops_blank_lines():
    req = ManualRecipeRequest(title="X", servings=2, raw_lines=["1 egg", "  ", "", "2 cups flour"])
    assert req.raw_lines == ["1 egg", "2 cups flour"]


def test_ingredient_update_all_optional():
    upd = IngredientUpdate(qty=3.0)
    assert upd.qty == 3.0
    assert upd.name is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_recipe_schemas.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `backend/app/recipes/schemas.py`:

```python
"""Pydantic request/response models for the recipes API."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class ImportRequest(BaseModel):
    url: str


class ManualRecipeRequest(BaseModel):
    title: str
    servings: int = 1
    raw_lines: list[str]

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()

    @field_validator("raw_lines")
    @classmethod
    def _drop_blank_lines(cls, v: list[str]) -> list[str]:
        return [line.strip() for line in v if line.strip()]


class IngredientUpdate(BaseModel):
    qty: float | None = None
    unit: str | None = None
    name: str | None = None
    ingredient_id: int | None = None


class IngredientRead(BaseModel):
    id: int
    raw_text: str
    qty: float | None
    unit: str | None
    ingredient_id: int | None
    ingredient_name: str | None
    parse_source: str
    needs_review: bool


class RecipeRead(BaseModel):
    id: int
    title: str
    servings: int
    source_url: str | None
    ingredients: list[IngredientRead]


class RecipeSummary(BaseModel):
    id: int
    title: str
    servings: int
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_recipe_schemas.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/recipes/schemas.py backend/tests/test_recipe_schemas.py
git commit -m "feat(backend): add recipe API schemas"
```

---

## Task 9: `recipes/service.py` — orchestrator

**Files:**
- Create: `backend/app/recipes/service.py`
- Test: `backend/tests/test_recipe_service.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_recipe_service.py` (scraper/parser/canonicalize all real except the LLM, which is mocked; or mock the seams — here we mock the library-facing functions and LLM):

```python
from unittest.mock import MagicMock, patch

from app.ingredients.parser import ParsedLine
from app.recipes.scraper import ScrapedRecipe
from app.recipes.service import create_from_manual, import_from_url
from app.models import Recipe, RecipeIngredient, Ingredient


def _stub_parse(raw_text, llm):
    table = {
        "2 cups all-purpose flour": ParsedLine(2.0, "cup", "all-purpose flour", "library"),
        "1 egg": ParsedLine(1.0, None, "egg", "library"),
        "a pinch of saffron": ParsedLine(None, None, "saffron", "library_low_confidence"),
    }
    return table[raw_text]


@patch("app.recipes.service.parse_line", side_effect=_stub_parse)
def test_manual_create_persists_recipe_and_flags(mock_parse, db_session):
    llm = MagicMock()
    # canonicalize: flour+egg known, saffron new
    flour = Ingredient(canonical_name="all purpose flour", aliases=[])
    egg = Ingredient(canonical_name="egg", aliases=[])
    db_session.add_all([flour, egg])
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {
            "all-purpose flour": CanonResult(flour.id, False),
            "egg": CanonResult(egg.id, False),
            "saffron": CanonResult(999, True),  # pretend-new id
        }
        recipe = create_from_manual(
            title="Test",
            servings=3,
            raw_lines=["2 cups all-purpose flour", "1 egg", "a pinch of saffron"],
            db=db_session,
            llm=llm,
        )

    saved = db_session.get(Recipe, recipe.id)
    assert saved.title == "Test"
    assert saved.default_servings == 3
    items = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
    assert len(items) == 3
    by_text = {i.raw_text: i for i in items}
    # low-confidence parse OR new ingredient → needs_review
    assert by_text["a pinch of saffron"].needs_review is True
    # clean known ingredient → not flagged
    assert by_text["1 egg"].needs_review is False


@patch("app.recipes.service.scrape_url")
@patch("app.recipes.service.parse_line", side_effect=_stub_parse)
def test_import_from_url_uses_scraper(mock_parse, mock_scrape, db_session):
    mock_scrape.return_value = ScrapedRecipe(
        title="Pancakes", servings=4, raw_lines=["1 egg"]
    )
    egg = Ingredient(canonical_name="egg", aliases=[])
    db_session.add(egg)
    db_session.flush()
    llm = MagicMock()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"egg": CanonResult(egg.id, False)}
        recipe = import_from_url("https://example.com/pancakes", db=db_session, llm=llm)

    saved = db_session.get(Recipe, recipe.id)
    assert saved.title == "Pancakes"
    assert saved.source_url == "https://example.com/pancakes"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_recipe_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `backend/app/recipes/service.py`:

```python
"""Orchestrates scrape → parse → canonicalize → persist. The only writer of Recipe rows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingredients.canonicalize import canonicalize_names
from app.ingredients.parser import parse_line
from app.llm.client import LLMClient
from app.models import Recipe, RecipeIngredient
from app.recipes.scraper import scrape_url

_LOW_CONFIDENCE_SOURCE = "library_low_confidence"


def _build_recipe(
    *, title: str, servings: int, source_url: str | None, raw_lines: list[str],
    db: Session, llm: LLMClient,
) -> Recipe:
    parsed = [(raw, parse_line(raw, llm)) for raw in raw_lines]
    canon = canonicalize_names([p.name for _, p in parsed], db, llm)

    recipe = Recipe(title=title, default_servings=servings, source_url=source_url)
    db.add(recipe)
    db.flush()

    for raw, p in parsed:
        result = canon[p.name]
        needs_review = (
            p.source == _LOW_CONFIDENCE_SOURCE
            or p.source == "llm"
            or p.qty is None
            or result.is_new
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                raw_text=raw,
                qty=p.qty,
                unit=p.unit,
                ingredient_id=result.ingredient_id,
                parse_source="manual" if source_url is None and p.source == "library" else p.source,
                needs_review=needs_review,
            )
        )
    db.flush()
    return recipe


def import_from_url(url: str, *, db: Session, llm: LLMClient) -> Recipe:
    scraped = scrape_url(url, llm)
    return _build_recipe(
        title=scraped.title,
        servings=scraped.servings or 1,
        source_url=url,
        raw_lines=scraped.raw_lines,
        db=db,
        llm=llm,
    )


def create_from_manual(
    *, title: str, servings: int, raw_lines: list[str], db: Session, llm: LLMClient
) -> Recipe:
    return _build_recipe(
        title=title, servings=servings, source_url=None, raw_lines=raw_lines, db=db, llm=llm
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_recipe_service.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/recipes/service.py backend/tests/test_recipe_service.py
git commit -m "feat(backend): add recipe import/create orchestration service"
```

---

## Task 10: `recipes/router.py` + register in `main.py`

**Files:**
- Create: `backend/app/recipes/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_recipes_router.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_recipes_router.py` (uses FastAPI TestClient with `get_db` overridden to the test session; service-level functions mocked so no scraping/LLM):

```python
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Ingredient, Recipe, RecipeIngredient


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed_recipe(db_session):
    ing = Ingredient(canonical_name="egg", aliases=[])
    db_session.add(ing)
    db_session.flush()
    recipe = Recipe(title="Test", default_servings=2)
    db_session.add(recipe)
    db_session.flush()
    ri = RecipeIngredient(
        recipe_id=recipe.id, raw_text="1 egg", qty=1.0, unit=None,
        ingredient_id=ing.id, parse_source="library", needs_review=True,
    )
    db_session.add(ri)
    db_session.flush()
    return recipe, ri, ing


def test_get_recipe_returns_ingredients(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)

    resp = client.get(f"/recipes/{recipe.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test"
    assert body["ingredients"][0]["ingredient_name"] == "egg"
    assert body["ingredients"][0]["needs_review"] is True
    app.dependency_overrides.clear()


def test_list_recipes(db_session):
    _seed_recipe(db_session)
    client = _client(db_session)

    resp = client.get("/recipes")

    assert resp.status_code == 200
    assert resp.json()[0]["title"] == "Test"
    app.dependency_overrides.clear()


def test_patch_ingredient_clears_flag(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)

    resp = client.patch(
        f"/recipes/{recipe.id}/ingredients/{ri.id}", json={"qty": 2.0}
    )

    assert resp.status_code == 200
    db_session.refresh(ri)
    assert ri.qty == 2.0
    assert ri.needs_review is False
    app.dependency_overrides.clear()


def test_manual_create_endpoint(db_session):
    client = _client(db_session)
    with patch("app.recipes.router.create_from_manual") as mock_create:
        recipe = Recipe(title="Manual", default_servings=1)
        db_session.add(recipe)
        db_session.flush()
        mock_create.return_value = recipe

        resp = client.post("/recipes", json={"title": "Manual", "servings": 1, "raw_lines": ["1 egg"]})

    assert resp.status_code == 201
    assert resp.json()["title"] == "Manual"
    app.dependency_overrides.clear()


def test_import_endpoint(db_session):
    client = _client(db_session)
    with patch("app.recipes.router.import_from_url") as mock_import:
        recipe = Recipe(title="Imported", default_servings=4, source_url="https://x.com")
        db_session.add(recipe)
        db_session.flush()
        mock_import.return_value = recipe

        resp = client.post("/recipes/import", json={"url": "https://x.com"})

    assert resp.status_code == 201
    assert resp.json()["title"] == "Imported"
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_recipes_router.py -v`
Expected: FAIL — `app.recipes.router` not found / route 404.

- [ ] **Step 3: Implement** `backend/app/recipes/router.py`:

```python
"""HTTP layer for recipes. Thin — delegates to the service and serializes models."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.client import LLMClient
from app.models import Ingredient, Recipe, RecipeIngredient
from app.recipes.scraper import ScrapeError
from app.recipes.schemas import (
    IngredientRead,
    IngredientUpdate,
    ImportRequest,
    ManualRecipeRequest,
    RecipeRead,
    RecipeSummary,
)
from app.recipes.service import create_from_manual, import_from_url

router = APIRouter(prefix="/recipes", tags=["recipes"])


def get_llm() -> LLMClient:
    return LLMClient()


def _serialize(recipe: Recipe, db: Session) -> RecipeRead:
    rows = db.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).scalars().all()
    name_by_id = {
        i.id: i.canonical_name
        for i in db.execute(select(Ingredient)).scalars().all()
    }
    ingredients = [
        IngredientRead(
            id=r.id,
            raw_text=r.raw_text,
            qty=r.qty,
            unit=r.unit,
            ingredient_id=r.ingredient_id,
            ingredient_name=name_by_id.get(r.ingredient_id),
            parse_source=r.parse_source,
            needs_review=r.needs_review,
        )
        for r in rows
    ]
    return RecipeRead(
        id=recipe.id,
        title=recipe.title,
        servings=recipe.default_servings,
        source_url=recipe.source_url,
        ingredients=ingredients,
    )


@router.post("/import", response_model=RecipeRead, status_code=201)
def import_recipe(body: ImportRequest, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    try:
        recipe = import_from_url(body.url, db=db, llm=llm)
    except ScrapeError as exc:
        raise HTTPException(status_code=422, detail=f"Could not import recipe: {exc}")
    db.commit()
    return _serialize(recipe, db)


@router.post("", response_model=RecipeRead, status_code=201)
def create_recipe(body: ManualRecipeRequest, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    if not body.raw_lines:
        raise HTTPException(status_code=422, detail="At least one ingredient line is required")
    recipe = create_from_manual(
        title=body.title, servings=body.servings, raw_lines=body.raw_lines, db=db, llm=llm
    )
    db.commit()
    return _serialize(recipe, db)


@router.get("", response_model=list[RecipeSummary])
def list_recipes(db: Session = Depends(get_db)):
    recipes = db.execute(select(Recipe).order_by(Recipe.created_at.desc())).scalars().all()
    return [RecipeSummary(id=r.id, title=r.title, servings=r.default_servings) for r in recipes]


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _serialize(recipe, db)


@router.patch("/{recipe_id}/ingredients/{ingredient_row_id}", response_model=RecipeRead)
def update_ingredient(
    recipe_id: int, ingredient_row_id: int, body: IngredientUpdate, db: Session = Depends(get_db)
):
    row = db.get(RecipeIngredient, ingredient_row_id)
    if row is None or row.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if body.qty is not None:
        row.qty = body.qty
    if body.unit is not None:
        row.unit = body.unit
    if body.ingredient_id is not None:
        row.ingredient_id = body.ingredient_id
    row.needs_review = False
    db.commit()
    recipe = db.get(Recipe, recipe_id)
    return _serialize(recipe, db)
```

- [ ] **Step 4: Register the router** in `backend/app/main.py`. Replace its contents with:

```python
from fastapi import FastAPI

from app.recipes.router import router as recipes_router

app = FastAPI(title="Bushel API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(recipes_router)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_recipes_router.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Run the full backend suite**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/recipes/router.py backend/app/main.py backend/tests/test_recipes_router.py
git commit -m "feat(backend): add recipes API router"
```

---

## Task 11: Frontend API client + types

**Files:**
- Create: `frontend/src/recipes/types.ts`
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/recipes/api.test.ts`

- [ ] **Step 1: Create** `frontend/src/recipes/types.ts`:

```typescript
export interface IngredientRead {
  id: number;
  raw_text: string;
  qty: number | null;
  unit: string | null;
  ingredient_id: number | null;
  ingredient_name: string | null;
  parse_source: string;
  needs_review: boolean;
}

export interface RecipeRead {
  id: number;
  title: string;
  servings: number;
  source_url: string | null;
  ingredients: IngredientRead[];
}

export interface RecipeSummary {
  id: number;
  title: string;
  servings: number;
}
```

- [ ] **Step 2: Write the failing test** `frontend/src/recipes/api.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { importRecipe, listRecipes, updateIngredient } from "../api";

afterEach(() => vi.restoreAllMocks());

describe("recipe api", () => {
  it("importRecipe posts the url", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 1, title: "X", servings: 2, source_url: null, ingredients: [] }), { status: 201 }),
    );
    const recipe = await importRecipe("https://example.com");
    expect(recipe.title).toBe("X");
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/recipes/import"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listRecipes fetches summaries", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "X", servings: 2 }]), { status: 200 }),
    );
    const list = await listRecipes();
    expect(list[0].title).toBe("X");
  });

  it("updateIngredient patches and returns the recipe", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 1, title: "X", servings: 2, source_url: null, ingredients: [] }), { status: 200 }),
    );
    const recipe = await updateIngredient(1, 5, { qty: 2 });
    expect(recipe.id).toBe(1);
  });

  it("throws on non-ok", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 422 }));
    await expect(importRecipe("bad")).rejects.toThrow();
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/recipes/api.test.ts`
Expected: FAIL — functions not exported.

- [ ] **Step 4: Append to** `frontend/src/api.ts` (keep the existing `BASE_URL` and `getHealth`):

```typescript
import type { RecipeRead, RecipeSummary } from "./recipes/types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export async function importRecipe(url: string): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return json<RecipeRead>(res);
}

export async function createRecipe(
  title: string,
  servings: number,
  rawLines: string[],
): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, servings, raw_lines: rawLines }),
  });
  return json<RecipeRead>(res);
}

export async function getRecipe(id: number): Promise<RecipeRead> {
  return json<RecipeRead>(await fetch(`${BASE_URL}/recipes/${id}`));
}

export async function listRecipes(): Promise<RecipeSummary[]> {
  return json<RecipeSummary[]>(await fetch(`${BASE_URL}/recipes`));
}

export async function updateIngredient(
  recipeId: number,
  rowId: number,
  patch: { qty?: number; unit?: string; name?: string; ingredient_id?: number },
): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes/${recipeId}/ingredients/${rowId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return json<RecipeRead>(res);
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run (from `frontend/`): `npm test -- src/recipes/api.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/recipes/types.ts frontend/src/api.ts frontend/src/recipes/api.test.ts
git commit -m "feat(frontend): add recipe API client functions and types"
```

---

## Task 12: `RecipeList` screen

**Files:**
- Create: `frontend/src/recipes/RecipeList.tsx`
- Test: `frontend/src/recipes/RecipeList.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/recipes/RecipeList.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecipeList } from "./RecipeList";

afterEach(() => vi.restoreAllMocks());

describe("RecipeList", () => {
  it("renders recipe titles from the API", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    );
    render(<RecipeList onOpen={() => {}} />);
    expect(await screen.findByText(/pancakes/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no recipes", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
    render(<RecipeList onOpen={() => {}} />);
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/recipes/RecipeList.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `frontend/src/recipes/RecipeList.tsx`:

```tsx
import { useEffect, useState } from "react";

import { listRecipes } from "../api";
import type { RecipeSummary } from "./types";

export function RecipeList({ onOpen }: { onOpen: (id: number) => void }) {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);

  useEffect(() => {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, []);

  if (recipes === null) return <p>Loading…</p>;
  if (recipes.length === 0) return <p>No recipes yet. Add one to get started.</p>;

  return (
    <ul>
      {recipes.map((r) => (
        <li key={r.id}>
          <button onClick={() => onOpen(r.id)}>
            {r.title} ({r.servings} servings)
          </button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `frontend/`): `npm test -- src/recipes/RecipeList.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeList.tsx frontend/src/recipes/RecipeList.test.tsx
git commit -m "feat(frontend): add recipe list screen"
```

---

## Task 13: `AddRecipe` screen

**Files:**
- Create: `frontend/src/recipes/AddRecipe.tsx`
- Test: `frontend/src/recipes/AddRecipe.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/recipes/AddRecipe.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddRecipe } from "./AddRecipe";

afterEach(() => vi.restoreAllMocks());

const recipeJson = { id: 7, title: "X", servings: 2, source_url: null, ingredients: [] };

describe("AddRecipe", () => {
  it("imports by URL and calls onCreated with the new id", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(recipeJson), { status: 201 }),
    );
    const onCreated = vi.fn();
    render(<AddRecipe onCreated={onCreated} />);

    await userEvent.type(screen.getByLabelText(/recipe url/i), "https://example.com/x");
    await userEvent.click(screen.getByRole("button", { name: /import/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(7));
  });

  it("shows an error when import fails", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("bad", { status: 422 }));
    render(<AddRecipe onCreated={() => {}} />);

    await userEvent.type(screen.getByLabelText(/recipe url/i), "https://bad");
    await userEvent.click(screen.getByRole("button", { name: /import/i }));

    expect(await screen.findByText(/couldn't import/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Ensure `@testing-library/user-event` is installed**

Run (from `frontend/`): `npm install -D @testing-library/user-event@^14`

- [ ] **Step 3: Run the test to verify it fails**

Run (from `frontend/`): `npm test -- src/recipes/AddRecipe.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement** `frontend/src/recipes/AddRecipe.tsx`:

```tsx
import { useState } from "react";

import { createRecipe, importRecipe } from "../api";

export function AddRecipe({ onCreated }: { onCreated: (id: number) => void }) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [servings, setServings] = useState(1);
  const [lines, setLines] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<{ id: number }>) {
    setBusy(true);
    setError(null);
    try {
      const recipe = await action();
      onCreated(recipe.id);
    } catch {
      setError("Couldn't import — check the URL or try manual entry.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <section>
        <h2>Import by URL</h2>
        <label>
          Recipe URL
          <input value={url} onChange={(e) => setUrl(e.target.value)} />
        </label>
        <button disabled={busy || !url} onClick={() => run(() => importRecipe(url))}>
          {busy ? "Importing…" : "Import"}
        </button>
      </section>

      <section>
        <h2>Or enter manually</h2>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Servings
          <input
            type="number"
            value={servings}
            onChange={(e) => setServings(Number(e.target.value))}
          />
        </label>
        <label>
          Ingredients (one per line)
          <textarea value={lines} onChange={(e) => setLines(e.target.value)} />
        </label>
        <button
          disabled={busy || !title.trim() || !lines.trim()}
          onClick={() =>
            run(() => createRecipe(title, servings, lines.split("\n")))
          }
        >
          {busy ? "Saving…" : "Save recipe"}
        </button>
      </section>

      {error && <p role="alert">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run (from `frontend/`): `npm test -- src/recipes/AddRecipe.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/recipes/AddRecipe.tsx frontend/src/recipes/AddRecipe.test.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add recipe import/manual entry screen"
```

---

## Task 14: `RecipeDetail` review screen

**Files:**
- Create: `frontend/src/recipes/RecipeDetail.tsx`
- Test: `frontend/src/recipes/RecipeDetail.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/recipes/RecipeDetail.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecipeDetail } from "./RecipeDetail";

afterEach(() => vi.restoreAllMocks());

const flaggedRecipe = {
  id: 1,
  title: "Pancakes",
  servings: 4,
  source_url: null,
  ingredients: [
    {
      id: 10, raw_text: "a pinch of saffron", qty: null, unit: null,
      ingredient_id: 5, ingredient_name: "saffron", parse_source: "library_low_confidence",
      needs_review: true,
    },
    {
      id: 11, raw_text: "1 egg", qty: 1, unit: null, ingredient_id: 6,
      ingredient_name: "egg", parse_source: "library", needs_review: false,
    },
  ],
};

describe("RecipeDetail", () => {
  it("shows the review banner with the flagged count", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(flaggedRecipe), { status: 200 }),
    );
    render(<RecipeDetail recipeId={1} />);
    expect(await screen.findByText(/1 item needs review/i)).toBeInTheDocument();
  });

  it("saving an edited qty calls PATCH and refreshes", async () => {
    const cleared = {
      ...flaggedRecipe,
      ingredients: [
        { ...flaggedRecipe.ingredients[0], qty: 1, needs_review: false },
        flaggedRecipe.ingredients[1],
      ],
    };
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(flaggedRecipe), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(cleared), { status: 200 }));

    render(<RecipeDetail recipeId={1} />);
    const qtyInput = await screen.findByLabelText(/qty for a pinch of saffron/i);
    await userEvent.clear(qtyInput);
    await userEvent.type(qtyInput, "1");
    await userEvent.click(screen.getByRole("button", { name: /save a pinch of saffron/i }));

    await waitFor(() =>
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining("/recipes/1/ingredients/10"),
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
    expect(await screen.findByText(/all items reviewed/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/recipes/RecipeDetail.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `frontend/src/recipes/RecipeDetail.tsx`:

```tsx
import { useEffect, useState } from "react";

import { getRecipe, updateIngredient } from "../api";
import type { IngredientRead, RecipeRead } from "./types";

function Row({
  recipeId,
  ingredient,
  onSaved,
}: {
  recipeId: number;
  ingredient: IngredientRead;
  onSaved: (recipe: RecipeRead) => void;
}) {
  const [qty, setQty] = useState(ingredient.qty?.toString() ?? "");
  const [unit, setUnit] = useState(ingredient.unit ?? "");

  async function save() {
    const updated = await updateIngredient(recipeId, ingredient.id, {
      qty: qty === "" ? undefined : Number(qty),
      unit: unit === "" ? undefined : unit,
    });
    onSaved(updated);
  }

  return (
    <li style={{ background: ingredient.needs_review ? "#fff3cd" : "transparent" }}>
      <span>{ingredient.raw_text}</span> → <strong>{ingredient.ingredient_name}</strong>
      <label>
        Qty for {ingredient.raw_text}
        <input value={qty} onChange={(e) => setQty(e.target.value)} />
      </label>
      <label>
        Unit for {ingredient.raw_text}
        <input value={unit} onChange={(e) => setUnit(e.target.value)} />
      </label>
      <button onClick={save}>Save {ingredient.raw_text}</button>
    </li>
  );
}

export function RecipeDetail({ recipeId }: { recipeId: number }) {
  const [recipe, setRecipe] = useState<RecipeRead | null>(null);

  useEffect(() => {
    getRecipe(recipeId).then(setRecipe).catch(() => setRecipe(null));
  }, [recipeId]);

  if (recipe === null) return <p>Loading…</p>;

  const flagged = recipe.ingredients.filter((i) => i.needs_review).length;

  return (
    <div>
      <h2>{recipe.title}</h2>
      {flagged > 0 ? (
        <p role="status">{flagged} item{flagged === 1 ? "" : "s"} need{flagged === 1 ? "s" : ""} review</p>
      ) : (
        <p role="status">All items reviewed ✓</p>
      )}
      <ul>
        {recipe.ingredients.map((ing) => (
          <Row key={ing.id} recipeId={recipe.id} ingredient={ing} onSaved={setRecipe} />
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `frontend/`): `npm test -- src/recipes/RecipeDetail.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeDetail.tsx frontend/src/recipes/RecipeDetail.test.tsx
git commit -m "feat(frontend): add recipe detail/review screen"
```

---

## Task 15: Wire screens into `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

- [ ] **Step 1: Update the failing test** `frontend/src/App.test.tsx` (replace the file; keeps a backend-status check and adds navigation):

```tsx
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    // health + empty recipe list
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
      }
      return Promise.resolve(new Response("[]", { status: 200 }));
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders the Bushel title and the recipe library by default", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: /bushel/i })).toBeInTheDocument();
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });

  it("has a way to navigate to add-recipe", async () => {
    render(<App />);
    expect(await screen.findByRole("button", { name: /add recipe/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/App.test.tsx`
Expected: FAIL — no "add recipe" button / no list.

- [ ] **Step 3: Implement** `frontend/src/App.tsx`:

```tsx
import { useState } from "react";

import { AddRecipe } from "./recipes/AddRecipe";
import { RecipeDetail } from "./recipes/RecipeDetail";
import { RecipeList } from "./recipes/RecipeList";

type View =
  | { name: "list" }
  | { name: "add" }
  | { name: "detail"; id: number };

export function App() {
  const [view, setView] = useState<View>({ name: "list" });

  return (
    <main>
      <h1>Bushel</h1>
      <nav>
        <button onClick={() => setView({ name: "list" })}>Recipes</button>
        <button onClick={() => setView({ name: "add" })}>Add recipe</button>
      </nav>

      {view.name === "list" && (
        <RecipeList onOpen={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "add" && (
        <AddRecipe onCreated={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "detail" && <RecipeDetail recipeId={view.id} />}
    </main>
  );
}
```

- [ ] **Step 4: Run it to verify it passes, then the full frontend suite**

Run (from `frontend/`): `npm test`
Expected: all pass (App + recipes + api tests).

- [ ] **Step 5: Verify the production build compiles**

Run (from `frontend/`): `npm run build`
Expected: `tsc -b && vite build` succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): wire recipe screens into app navigation"
```

---

## Task 16: End-to-end smoke test (manual, human-run)

This task is **not** automated (it makes real scraping + Claude calls). Run it once after the suite is green to confirm the live pipeline works.

**Files:** none (manual verification).

- [ ] **Step 1: Set a real Anthropic key** in `backend/.env` (`ANTHROPIC_API_KEY=sk-ant-...`).

- [ ] **Step 2: Bring up the stack**

Run (from repo root): `docker compose up --build -d` (rebuilds the api image with the new deps). Wait for health: `curl -s http://localhost:8000/health`.

- [ ] **Step 3: Import a real recipe**

Run: `curl -s -X POST http://localhost:8000/recipes/import -H 'Content-Type: application/json' -d '{"url":"https://www.allrecipes.com/recipe/21014/good-old-fashioned-pancakes/"}' | head -c 800`
Expected: a 201 JSON `RecipeRead` with a title and several parsed ingredients, each with `ingredient_name` and a `needs_review` flag.

- [ ] **Step 4: Open the UI**

Visit `http://localhost:5173`, confirm the recipe appears in the list, open it, and verify the review screen highlights any flagged rows and that editing a row clears its flag.

- [ ] **Step 5: Tear down**

Run: `docker compose down`

- [ ] **Step 6: Record the result** in the PR/commit notes (no code change). If parsing quality is poor, note specific failing lines for a follow-up tuning pass — do not block Phase 2 completion on edge-case parse quality (per the spec's "never hard-fail on parse quality" principle).

---

## Self-Review

**1. Spec coverage:**
- URL import (recipe-scrapers + Claude fallback) → Task 7 (`scraper.py`), Task 9 (`import_from_url`), Task 10 (`/recipes/import`).
- Manual entry through the same pipeline → Task 9 (`create_from_manual`), Task 10 (`POST /recipes`), Task 13 (form).
- Library-first parsing + Claude fallback, `parse_source` → Task 5 (`parser.py`).
- Normalize + alias canonicalization, Claude only for new, new ingredients get category + default_purchase_unit → Task 3 (`normalize.py`), Task 4 (LLM contract), Task 6 (`canonicalize.py`).
- Batched canonicalization call → Task 6 (one `canonicalize_ingredients` call for all misses).
- `needs_review` flag + migration → Task 2; flag-setting logic → Task 9; review UI → Task 14; clear-on-edit → Task 10 (`PATCH`) + Task 14.
- API endpoints (import, manual, get, list, patch) → Task 10; identical `RecipeRead` shape → Task 8 + Task 10 `_serialize`.
- Three React screens → Tasks 12, 13, 14; navigation → Task 15.
- "Never hard-fail on parse quality" → Task 5 (`library_low_confidence` fallback), Task 6 (LLM-unavailable → create flagged new), Task 9 (flagging), Task 7 (only true fetch/no-ingredients failures raise → 422 in Task 10).
- LLM mocked in all automated tests → every backend test patches/mocks `LLMClient`; live calls only in Task 16 (manual).

No spec requirement is left without a task.

**2. Placeholder scan:** No TBD/TODO. Every code step has complete, runnable content. The two "verify the installed library API and adjust the adapter" steps (Tasks 5 and 7) are explicit, bounded verification actions against a named command — not vague placeholders — and are necessary because third-party library shapes are version-specific.

**3. Type/name consistency:**
- `LLMClient` methods (`parse_ingredient_line`, `canonicalize_ingredients`, `scrape_recipe`) and return types (`ParsedLineLLM`, `CanonicalizeResult`/`CanonicalizeOne`/`NewIngredientLLM`, `ScrapedRecipeLLM`) are defined in Task 4 and consumed consistently in Tasks 5, 6, 7.
- `ParsedLine(qty, unit, name, source)` defined in Task 5, consumed in Task 9.
- `CanonResult(ingredient_id, is_new)` defined in Task 6, consumed in Task 9.
- `ScrapedRecipe(title, servings, raw_lines)` defined in Task 7, consumed in Task 9.
- `RecipeRead`/`IngredientRead`/`RecipeSummary` shapes match between backend schemas (Task 8), the router serializer (Task 10), and the frontend types (Task 11) — field names `id, raw_text, qty, unit, ingredient_id, ingredient_name, parse_source, needs_review` and `id, title, servings, source_url, ingredients` are identical on both sides.
- Frontend API functions (`importRecipe`, `createRecipe`, `getRecipe`, `listRecipes`, `updateIngredient`) defined in Task 11 and consumed in Tasks 12–14.
- Model id `claude-haiku-4-5` used consistently (Task 4 `MODEL` constant; asserted in Task 4 test).

**4. Note on `parse_source` values:** the column stores `library` | `llm` | `manual` | `library_low_confidence`. The spec named `library`/`llm`/`manual`; `library_low_confidence` is an added internal value that also drives `needs_review`. This is consistent across Tasks 5 and 9; if a stricter enum is desired later, it's a single-place change.
```

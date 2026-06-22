# Keep quantities in extraction + normalize units on save — design

Date: 2026-06-22

## Goal

Two related refinements to recipe ingredient handling:

1. **Extraction keeps quantities.** The LLM ingredient extractor (`extract_ingredients`)
   currently returns bare ingredient names, dropping amounts. Pasted "2 tbsp olive oil"
   should come back as "2 tablespoons olive oil" (quantity + unit preserved).
2. **Units are normalized to a canonical form on save.** Whether a unit arrives from
   extraction, the parser, or the user typing it on the recipe edit screen, it should be
   stored/displayed in the same canonical form the grocery-list consolidation uses
   (e.g. "tbsp" → "tablespoon", "cups" → "cup"), so the recipe and the consolidation line up.

## Background / current state

- **`LLMClient.extract_ingredients(text)`** (`backend/app/llm/client.py`) has a system
  prompt that returns only ingredient lines; it does not instruct keeping quantities, and in
  practice drops them.
- **Unit normalization already exists** but is private and only used during consolidation:
  `_normalize_unit(unit)` in `backend/app/consolidate/units.py` lowercases, collapses a
  trailing plural "s" (singularize: "cups"→"cup", "cloves"→"clove"), and maps cooking aliases
  (`tbsp`/`tbs`/`tb`→`tablespoon`, `t`/`tsp`→`teaspoon`, `c`→`cup`, `oz`→`ounce`, `lb`/`lbs`→
  `pound`, etc.). Unknown units pass through (after singularization). It is called only by
  `consolidate(...)` and `convert_qty(...)` in the same file; nothing else (incl. tests)
  imports it.
- **Recipe ingredient units are stored raw** — no normalization on any write path:
  - `_build_recipe` (`recipes/service.py`) stores `parsed.unit` from `parse_line`.
  - `add_ingredient` (`recipes/service.py`) stores `parsed.unit`.
  - `update_ingredient` (PATCH, `recipes/router.py`) sets `row.unit = body.unit` (the value
    typed on the edit screen) when not None.
- The recipe edit screen (`RecipeDetail.tsx`) displays whatever unit the server returns; it
  has no client-side unit logic.

## Architecture / approach

Backend-only. Normalization happens **on save**, at the few places a `RecipeIngredient.unit`
is written, reusing the existing consolidation normalizer (now exposed as `normalize_unit`).
This guarantees the stored recipe unit equals the consolidation grouping key, so "tbsp" and
"tablespoon" are identical everywhere. Extraction is widened (prompt) to keep amounts; the
kept amounts then flow through the unchanged parse→canonicalize→create pipeline, where the
unit gets normalized like any other.

## Backend changes

### 1. Expose the normalizer (`consolidate/units.py`)
- Rename `_normalize_unit` → `normalize_unit` (public) and update its two internal callers
  (`consolidate` and `convert_qty`). Behavior unchanged.

### 2. Normalize units on every recipe-ingredient write (`recipes/service.py`, `recipes/router.py`)
- `recipes/service.py`: `from app.consolidate.units import normalize_unit`.
  - `_build_recipe`: store `unit=normalize_unit(p.unit)` instead of `p.unit`.
  - `add_ingredient`: store `unit=normalize_unit(parsed.unit)` instead of `parsed.unit`.
- `recipes/router.py` `update_ingredient` (PATCH): import `normalize_unit`; when `body.unit`
  is not None, set `row.unit = normalize_unit(body.unit)`. (`normalize_unit` returns None for
  blank/whitespace, which correctly clears the unit.)

This covers manual create, URL import, the extract→Save path (all via `_build_recipe`),
single-ingredient add, and edit-screen save.

### 3. Extraction keeps quantities (`llm/client.py`)
- Update the `extract_ingredients` system prompt to keep the quantity and unit when present
  (e.g. "2 tablespoons olive oil", "1 lb ground turkey"); ingredients with no amount stay as
  just the name. Everything else about the prompt (ignore title/headers/steps, split compound
  comma lines, drop prep notes) is unchanged.

## Frontend changes

None. The edit screen already renders the server's unit value, which is now normalized; the
extract flow already populates the textarea (now with richer lines).

## Testing (TDD)

- **`tests/test_units.py`:** `normalize_unit` is public and normalizes aliases ("tbsp" →
  "tablespoon"), singularizes ("cups" → "cup"), passes through unknown units, and returns
  None for None/blank. (Adjust any existing assertions that referenced the old name — none do
  today.)
- **`tests/test_recipe_service.py`:** with `parse_line` stubbed to return `unit="tbsp"`,
  `add_ingredient` stores `unit="tablespoon"`; `_build_recipe` (via `create_from_manual`)
  normalizes a "tbsp" line to "tablespoon".
- **`tests/test_recipes_router.py`:** PATCH `update_ingredient` with `{"unit": "tbsp"}`
  stores and returns "tablespoon".
- **`tests/test_llm_client.py`:** the `extract_ingredients` system prompt instructs keeping
  the quantity/unit (assert the system string mentions quantity).

## Out of scope / non-goals

- Backfilling/normalizing units on existing recipes (only new saves/edits normalize).
- Any frontend change.
- Changing the consolidation normalizer's behavior (its singularization quirks, e.g.
  "pinches"→"pinche", are preserved as-is so recipe and consolidation stay 1:1).
- Per-ingredient "default unit" suggestions or unit conversion on the edit screen.

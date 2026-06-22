# Keep quantities + normalize units on save — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LLM extractor keep ingredient quantities, and normalize every recipe-ingredient unit to its canonical form on save (so "tbsp" is stored/shown as "tablespoon", matching consolidation).

**Architecture:** Backend-only. Expose the existing consolidation unit normalizer as `normalize_unit` and apply it on the three recipe-ingredient write paths; widen the `extract_ingredients` prompt to keep amounts. No frontend or migration changes.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic + Anthropic structured output (backend, `uv` + pytest).

---

## Conventions

**Backend tests** run against the isolated test Postgres `bushel_test` on port 5544 (NOT the dev DB on 5432 — `conftest.py` drops all tables on teardown). Always:

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest <args>
```

---

## File Structure

- Modify `backend/app/consolidate/units.py` — rename `_normalize_unit` → `normalize_unit` (public); update its two internal callers.
- Modify `backend/app/recipes/service.py` — normalize unit in `_build_recipe` and `add_ingredient`.
- Modify `backend/app/recipes/router.py` — normalize unit in `update_ingredient` (PATCH).
- Modify `backend/app/llm/client.py` — `extract_ingredients` prompt keeps quantity + unit.
- Tests: `backend/tests/test_units.py`, `backend/tests/test_recipe_service.py`, `backend/tests/test_recipes_router.py`, `backend/tests/test_llm_client.py`.

Task order: Task 1 exposes `normalize_unit`; Tasks 2–3 use it; Task 4 (prompt) is independent.

---

## Task 1: Expose `normalize_unit`

**Files:**
- Modify: `backend/app/consolidate/units.py`
- Test: `backend/tests/test_units.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_units.py`, change the import line to:

```python
from app.consolidate.units import consolidate, convert_qty, normalize_unit
```

Add these tests:

```python
def test_normalize_unit_aliases_and_singularizes():
    assert normalize_unit("tbsp") == "tablespoon"
    assert normalize_unit("Tbsp") == "tablespoon"
    assert normalize_unit("tsp") == "teaspoon"
    assert normalize_unit("cups") == "cup"
    assert normalize_unit("cloves") == "clove"


def test_normalize_unit_passthrough_and_none():
    assert normalize_unit("pinch") == "pinch"
    assert normalize_unit(None) is None
    assert normalize_unit("   ") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_units.py -k normalize_unit -v
```
Expected: FAIL — `normalize_unit` is not exported (currently `_normalize_unit`).

- [ ] **Step 3: Rename to public + update callers**

In `backend/app/consolidate/units.py`:
- Rename the function `def _normalize_unit(unit: str | None) -> str | None:` to `def normalize_unit(unit: str | None) -> str | None:`.
- Update its two call sites in the same file:
  - In `consolidate(...)`: `unit = _normalize_unit(raw_unit)` → `unit = normalize_unit(raw_unit)`.
  - In `convert_qty(...)`: `fu = _normalize_unit(from_unit)` → `fu = normalize_unit(from_unit)` and `tu = _normalize_unit(to_unit)` → `tu = normalize_unit(to_unit)`.

(There are no other references to `_normalize_unit` anywhere in the codebase.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_units.py -v
```
Expected: PASS (existing consolidation/convert tests + the 2 new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/app/consolidate/units.py backend/tests/test_units.py
git commit -m "refactor(units): expose normalize_unit (was _normalize_unit)"
```

---

## Task 2: Normalize units in the recipe service write paths

**Files:**
- Modify: `backend/app/recipes/service.py`
- Test: `backend/tests/test_recipe_service.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_recipe_service.py` (it imports `MagicMock, patch`, `ParsedLine`, `create_from_manual`, `add_ingredient`, `Recipe, RecipeIngredient, Ingredient`):

```python
@patch("app.recipes.service.parse_line")
def test_add_ingredient_normalizes_unit(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(2.0, "tbsp", "olive oil", "library")
    oil = Ingredient(canonical_name="olive oil", aliases=[])
    db_session.add(oil)
    recipe = Recipe(title="T", default_servings=1)
    db_session.add(recipe)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"olive oil": CanonResult(oil.id, False)}
        add_ingredient(db_session, recipe.id, "2 tbsp olive oil", llm=MagicMock())

    row = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).one()
    assert row.unit == "tablespoon"


@patch("app.recipes.service.parse_line")
def test_build_recipe_normalizes_unit(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(2.0, "tbsp", "olive oil", "library")
    oil = Ingredient(canonical_name="olive oil", aliases=[])
    db_session.add(oil)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"olive oil": CanonResult(oil.id, False)}
        recipe = create_from_manual(
            title="T", servings=1, raw_lines=["2 tbsp olive oil"], db=db_session, llm=MagicMock()
        )

    row = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).one()
    assert row.unit == "tablespoon"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipe_service.py -k normalizes_unit -v
```
Expected: FAIL — units stored as "tbsp", not normalized.

- [ ] **Step 3: Apply normalization in the service**

In `backend/app/recipes/service.py`:
- Add the import (with the other `app.*` imports): `from app.consolidate.units import normalize_unit`.
- In `_build_recipe`, change the `RecipeIngredient(...)` field `unit=p.unit,` to `unit=normalize_unit(p.unit),`.
- In `add_ingredient`, change the `RecipeIngredient(...)` field `unit=parsed.unit,` to `unit=normalize_unit(parsed.unit),`.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipe_service.py -v
```
Expected: PASS (existing + 2 new). The existing tests use already-canonical units ("cup", `None`), which `normalize_unit` returns unchanged.

- [ ] **Step 5: Commit**

```bash
git add backend/app/recipes/service.py backend/tests/test_recipe_service.py
git commit -m "feat(recipes): normalize ingredient units on create/import/add"
```

---

## Task 3: Normalize unit on the edit-screen save (PATCH)

**Files:**
- Modify: `backend/app/recipes/router.py`
- Test: `backend/tests/test_recipes_router.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_recipes_router.py` (it has `_client`, `_seed_recipe`; `_seed_recipe` returns `recipe, ri, ing` where `ri` is a RecipeIngredient):

```python
def test_patch_ingredient_normalizes_unit(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.patch(f"/recipes/{recipe.id}/ingredients/{ri.id}", json={"unit": "tbsp"})
    assert resp.status_code == 200
    db_session.refresh(ri)
    assert ri.unit == "tablespoon"
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -k patch_ingredient_normalizes -v
```
Expected: FAIL — PATCH stores "tbsp" verbatim.

- [ ] **Step 3: Apply normalization in the PATCH handler**

In `backend/app/recipes/router.py`:
- Add the import (with the other `app.*` imports): `from app.consolidate.units import normalize_unit`.
- In `update_ingredient`, change:

```python
    if body.unit is not None:
        row.unit = body.unit
```

to:

```python
    if body.unit is not None:
        row.unit = normalize_unit(body.unit)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -v
```
Expected: PASS (existing recipe-router tests + the new one). The existing `test_patch_ingredient_clears_flag` patches only `qty`, so it's unaffected.

- [ ] **Step 5: Commit**

```bash
git add backend/app/recipes/router.py backend/tests/test_recipes_router.py
git commit -m "feat(recipes): normalize ingredient unit on edit-screen save"
```

---

## Task 4: Extraction keeps quantities

**Files:**
- Modify: `backend/app/llm/client.py`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_llm_client.py` (it imports `MagicMock, patch` and `ExtractedIngredientsLLM`):

```python
@patch("app.llm.client.anthropic.Anthropic")
def test_extract_ingredients_prompt_keeps_quantities(mock_anthropic):
    mock_anthropic.return_value.messages.parse.return_value = MagicMock(
        stop_reason="end_turn", parsed_output=ExtractedIngredientsLLM(lines=[])
    )
    LLMClient(api_key="sk-test").extract_ingredients("some recipe text")
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    assert "quantity" in kwargs["system"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_llm_client.py -k keeps_quantities -v
```
Expected: FAIL — the current prompt doesn't mention quantity.

- [ ] **Step 3: Update the prompt**

In `backend/app/llm/client.py`, replace the `extract_ingredients` `system=(...)` string with:

```python
            system=(
                "You extract the ingredient list from pasted recipe text. Return only the "
                "ingredients, one per entry in `lines`. Keep the quantity and unit when "
                "present (e.g. '2 tablespoons olive oil', '1 lb ground turkey'); for "
                "ingredients with no amount, return just the name. Ignore the recipe title, "
                "section headers (such as 'Ingredients' or 'Steps'), and any numbered or "
                "instructional steps. If a single line lists multiple ingredients (e.g. "
                "comma-separated), split it into one entry per ingredient. Drop preparation "
                "notes (e.g. 'cut into wedges', 'chopped')."
            ),
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_llm_client.py -v
```
Expected: PASS (existing extract test + new prompt test).

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/client.py backend/tests/test_llm_client.py
git commit -m "feat(llm): keep quantities + units when extracting ingredients"
```

---

## Task 5: Full verification

- [ ] **Step 1: Full backend suite**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest -q
```
Expected: all tests pass.

- [ ] **Step 2: Frontend suite + build (no frontend changes, but confirm nothing broke)**

```bash
cd frontend && npm test && npm run build
```
Expected: all tests pass; build clean.

- [ ] **Step 3: Manual smoke (optional)**

Add recipe → paste a recipe block with amounts (e.g. "2 tbsp olive oil") → Extract: the textarea keeps the amounts. Save → on the detail page the unit shows "tablespoon". Edit a row's unit to "tsp" and Save → it shows "teaspoon".

---

## Self-Review notes (for the implementer)

- **Spec coverage:** expose normalizer → Task 1; normalize on create/import/add → Task 2; normalize on edit-screen save (PATCH) → Task 3; extraction keeps quantities → Task 4. No frontend/migration (per spec).
- **Consistency:** `normalize_unit` (single public function in `consolidate/units.py`) is the one normalizer used by consolidation AND all three recipe write paths, guaranteeing recipe units equal the consolidation grouping key. `normalize_unit(None)` → None and `normalize_unit("  ")` → None are relied on (PATCH clears unit on blank).
- **Existing-test safety:** `test_units.py` only imported `consolidate, convert_qty` (now also `normalize_unit`); `_normalize_unit` had no external references. Existing service/router tests use already-canonical units, so normalization is a no-op for them.

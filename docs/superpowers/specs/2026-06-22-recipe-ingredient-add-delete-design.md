# Add / remove a single recipe ingredient — design

Date: 2026-06-22

## Goal

Let the user add a single ingredient to an existing recipe, and remove a single
ingredient, from the recipe detail page (backed by the `recipes/` API).

Bulk paste + LLM parsing on the Add-recipe page is explicitly **out of scope** here and
deferred to a later iteration.

## Background / current state

- **Recipes API** (`backend/app/recipes/router.py`): create (manual `raw_lines` / import),
  list, get, and `PATCH /recipes/{id}/ingredients/{row_id}` (edits qty/unit/ingredient_id,
  clears `needs_review`). There is **no add-ingredient and no delete-ingredient endpoint.**
- **Parse pipeline** (`backend/app/recipes/service.py` `_build_recipe`): each raw line goes
  through `parse_line` (library-first, LLM fallback) → `canonicalize_names`, producing a
  `RecipeIngredient` with `qty`, `unit`, `ingredient_id`, `parse_source`, and a
  `needs_review` flag. The flag rule at creation is:
  `needs_review = source == "library_low_confidence" or source == "llm" or qty is None or result.is_new`.
- `_serialize(recipe, db)` builds the `RecipeRead` response (used by get/patch).
- **Frontend** `RecipeDetail.tsx` renders each ingredient row (raw text → matched
  ingredient, editable qty/unit, "Change" match, "Needs review" pill). The api client
  (`api.ts`) has `getRecipe`, `updateIngredient`, etc. — no add/delete ingredient calls.
- `RecipeIngredient.recipe_id` is a FK with `ON DELETE CASCADE`; rows are deleted directly.

## Backend changes

### Add an ingredient — `POST /recipes/{recipe_id}/ingredients`
- Request body: `{ "raw_text": str }` (new `AddIngredientRequest` schema; reject blank/
  whitespace-only with 422, mirroring `ManualRecipeRequest`'s title validator).
- Service `add_ingredient(recipe_id, raw_text, db, llm)`:
  - 404 (raise a `RecipeNotFoundError`-style not-found) if the recipe doesn't exist.
  - `parse_line(raw_text, llm)` → `canonicalize_names([parsed.name], db, llm)`.
  - Create a `RecipeIngredient(recipe_id, raw_text, qty, unit, ingredient_id, parse_source,
    needs_review)`. Reuse the **same `needs_review` rule** as `_build_recipe`. For
    `parse_source`, a hand-added line is a manual entry: `parse_source = "manual" if
    parsed.source == "library" else parsed.source` (i.e. `"manual"`, `"llm"`, or
    `"library_low_confidence"`).
  - Commit; return the updated `RecipeRead` via `_serialize` with status `201` (a row was
    created, consistent with `POST /recipes`).
- To avoid duplicating the `needs_review` rule, extract a tiny helper in `service.py`
  (e.g. `_needs_review(source, qty, is_new) -> bool`) and use it in both `_build_recipe`
  and `add_ingredient`.

### Delete an ingredient — `DELETE /recipes/{recipe_id}/ingredients/{row_id}`
- Service `delete_ingredient(recipe_id, row_id, db)`:
  - Load the row; 404 if it doesn't exist or `row.recipe_id != recipe_id` (same guard the
    existing PATCH endpoint uses).
  - Delete the row; commit; return the updated `RecipeRead`.
- Returns `200` with the updated `RecipeRead` (consistent with PATCH; lets the frontend
  re-render without a refetch).

## Frontend changes (`RecipeDetail.tsx`)

- **Add row:** below the ingredient list, an "Add an ingredient" text input + "Add" button.
  On submit, call `addIngredient(recipeId, rawText.trim())`; on success, replace the recipe
  state with the response and clear the input. The new row appears in the list, flagged
  "Needs review" when uncertain, and is editable/deletable like the rest. Disable the
  button when the input is empty; surface failures via `ErrorBanner`.
- **Delete control:** a 🗑 button on each ingredient row (`aria-label="Delete <raw_text>"`),
  guarded by a `window.confirm`. On confirm, call `deleteIngredient(recipeId, row.id)` and
  replace recipe state with the response. Surface failures via `ErrorBanner`.
- **api.ts:** add `addIngredient(recipeId, rawText): Promise<RecipeRead>` (`POST`) and
  `deleteIngredient(recipeId, rowId): Promise<RecipeRead>` (`DELETE`).

## Testing (TDD)

- **Backend** (`tests/test_recipes_router.py`, with mocked LLM/parse as the existing
  create tests do):
  - Add: 201 returns recipe with the new row; parsed qty/unit/ingredient populated;
    `needs_review` set per the rule (e.g. a clean "2 cups flour" not flagged; an unparseable
    line flagged); 404 for a missing recipe; 422 for blank `raw_text`.
  - Delete: removes the row and returns the updated recipe; 404 when the row is missing or
    belongs to a different recipe.
  - A service test for `_needs_review`/`add_ingredient` parsing behavior.
- **Frontend** (`RecipeDetail.test.tsx`, `api.test.ts` / `krogerApi.test.ts` style):
  - Add: typing a line + clicking Add calls `addIngredient` and renders the new row; input
    clears.
  - Delete: clicking 🗑 + confirming calls `deleteIngredient` and the row disappears;
    cancelling the confirm does nothing.
  - api client tests for the two new functions (paths/methods).

## Out of scope / non-goals

- Bulk paste of multiple ingredients and dedicated LLM block-parsing (deferred).
- Changes to the Add-recipe (new recipe) screen.
- Reordering ingredients; editing `raw_text` of an existing row.
- Undo for delete (a confirm prompt is the safeguard).

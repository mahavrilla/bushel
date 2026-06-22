# Recipe search, delete, and clearer ingredient mapping — design

Date: 2026-06-22

## Goal

Three related improvements to recipe management in Bushel:

1. **Search recipes** — filter the Recipes list by title.
2. **Delete recipes** — remove a recipe entirely, including from the active grocery list.
3. **Clearer ingredient-mapping page** — rework the recipe-detail page so each row
   reads plainly and lets the user fix which canonical ingredient a row maps to.

These are independent features that can be built and shipped in order.

## Background / current state

- **Recipes API** (`backend/app/recipes/router.py`) supports import, manual create,
  list (`GET /recipes`, ordered by `created_at desc`), get, and PATCH of an ingredient
  row. There is **no delete** and **no search**.
- **Recipe list UI** (`frontend/src/recipes/RecipeList.tsx`) renders every recipe with
  an "Add to list" button. No filter, no delete.
- **Recipe detail UI** (`frontend/src/recipes/RecipeDetail.tsx`) shows each parsed line
  as `raw_text → ingredient_name` with editable qty/unit and a per-row Save button, plus
  a "Needs review" pill. Users report it is dense and the row's meaning is unclear, and
  there is no way to fix a wrong/missing ingredient match from the UI.
- The PATCH endpoint (`/recipes/{recipe_id}/ingredients/{row_id}`) already accepts an
  `ingredient_id`, but **there is no endpoint to list, search, or create canonical
  ingredients**, so the UI cannot offer a picker today.
- **Cascade behavior** (`backend/app/models.py`): `RecipeIngredient.recipe_id` and
  `GroceryListRecipe.recipe_id` both use `ON DELETE CASCADE`. The consolidated
  `GroceryListItem` snapshots are not FK-linked to recipes — they are recomputed from
  `GroceryListRecipe` memberships.
- **Consolidation service** (`backend/app/consolidate/service.py`) exposes
  `recompute_draft(db)` and `remove_recipe(db, recipe_id)`, which the delete flow reuses.

## Feature 1 — Search recipes

**Approach:** client-side filter. No backend change.

- Add a search `Input` above the list in `RecipeList.tsx`.
- Filter the already-fetched recipes by case-insensitive substring match on `title`.
- Empty query shows all recipes. A query with no matches shows an empty-state message
  (e.g. "No recipes match that search.") distinct from the "no recipes yet" state.

**Rationale:** personal app with a modest recipe count; client-side filtering is instant
and adds no API surface. If the catalog ever grows large, a server-side `q` param can be
added later without changing the UI contract.

## Feature 2 — Delete recipes

**Backend:** `DELETE /recipes/{recipe_id}`

- 404 if the recipe does not exist.
- Delete the recipe row. `ON DELETE CASCADE` removes its `RecipeIngredient` rows and any
  `GroceryListRecipe` membership.
- After deletion, call `recompute_draft(db)` so the active grocery list drops the recipe's
  contribution and re-consolidates remaining recipes/staples. (This realizes the chosen
  behavior: deleting a recipe also removes it from the active list.)
- Returns `204 No Content`.
- Logic lives in the recipes service (e.g. `delete_recipe(db, recipe_id)`); the router
  stays thin and commits.

**Frontend:**

- Add a delete control (🗑, `aria-label` "Delete <title>") to each `RecipeList` row.
- On click, show a confirmation (native `confirm` or a small dialog) — "Delete <title>?
  This also removes it from your grocery list."
- On confirm: call delete, then refresh the list. Surface failures via the existing
  `ErrorBanner` pattern.

## Feature 3 — Clearer ingredient-mapping page

**New backend — ingredients router** (`backend/app/ingredients/router.py`, registered in
`main.py`):

- `GET /ingredients?q=<text>` — case-insensitive substring search over `canonical_name`,
  returns a list of `{ id, canonical_name }` capped at 20, ordered by `canonical_name`.
  An empty or missing `q` returns an empty list (the picker only queries once the user
  types).
- `POST /ingredients` — body `{ name }`; normalizes via `normalize_name`, creates the
  canonical `Ingredient` if it does not already exist (reusing the existing lookup so we
  do not create duplicates), returns `{ id, canonical_name }` with `201`. If a matching
  canonical ingredient already exists, return that one (idempotent on normalized name).

**Frontend — `RecipeDetail.tsx` rework:**

- Add a one-line intro above the rows: *"Each line from your recipe is matched to a
  grocery ingredient. Fix the amount or the match if it's wrong."*
- Restructure each row to read top-to-bottom with explicit labels:
  ```
  2 cloves garlic                              [Needs review]
    Matched to:  Garlic            [ Change ]
    Amount:  [ 2 ]   Unit: [ clove ]           [ Save ]
  ```
  - Raw recipe text is the row heading.
  - "Matched to" names the canonical ingredient, with a **Change** control.
  - "Amount" / "Unit" labels replace the bare arrow + unlabeled boxes.
  - "Needs review" pill only when `needs_review` is true; keep the amber row treatment.
  - Keep a **per-row Save button** for qty/unit (confirmed with user; no autosave).
- **Change the match:** the Change control reveals a typeahead that calls
  `GET /ingredients?q=`. Results are selectable; when the typed text matches nothing,
  offer a *"Create '<typed name>'"* action that calls `POST /ingredients` then re-maps.
  Selecting or creating an ingredient issues the existing PATCH with the new
  `ingredient_id`; the server response (which clears `needs_review`) updates the page.

## API client + types (frontend)

- `frontend/src/api.ts`: add `deleteRecipe(id)`, `searchIngredients(q)`,
  `createIngredient(name)`. Reuse existing `ApiError` handling.
- `frontend/src/recipes/types.ts`: add an `IngredientOption` type (`{ id, canonical_name }`).

## Testing (TDD)

Follow the existing test layout; write tests before implementation.

- **Backend:**
  - `tests/test_recipes_router.py` — delete: 204 on success, 404 when missing, recipe gone
    afterward, and a recipe-on-list case asserting the draft recomputes (item dropped).
  - New `tests/test_ingredients_router.py` (and service tests if logic warrants) — search
    matching/cap, create new, create idempotent on existing normalized name.
- **Frontend:**
  - `RecipeList.test.tsx` — search filters by title; no-match empty state; delete calls API
    after confirm and refreshes; cancel does nothing.
  - `RecipeDetail.test.tsx` — new labels render; Change opens the picker, searching lists
    results, selecting re-maps (PATCH with `ingredient_id`), and "Create" path creates then
    re-maps; Save still patches qty/unit.
  - `api.test.ts` — new client functions hit the right paths/methods and parse responses.

## Out of scope

- Server-side recipe search/pagination.
- Editing canonical ingredient metadata (category, aliases, default purchase unit) — only
  search and create are added.
- Bulk delete, soft delete / trash, or undo.
- Any unit-alias settings screen (`consolidate/units.py` remains a hardcoded table).

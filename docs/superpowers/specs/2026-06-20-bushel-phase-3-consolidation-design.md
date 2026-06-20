# Bushel Phase 3 — Consolidation Design Spec

**Date:** 2026-06-20
**Status:** Approved design, pending implementation plan
**Builds on:** Phase 1 (schema + Docker foundation) and Phase 2 (recipes with parsed `qty`/`unit` + canonical ingredients). See `2026-06-19-bushel-design.md` (overall) and the Phase 2 spec.

## Summary

Phase 3 builds the consolidation subsystem: the user assembles a single active "draft" grocery
list by adding recipes (each with a target servings count); the system scales each recipe's
ingredient quantities, merges identical canonical ingredients across recipes, and sums their
quantities using `pint` for unit conversion — keeping incompatible units (e.g. cloves + tbsp)
as separate sub-quantities rather than fabricating a wrong combined total. The result is a
consolidated, category-grouped grocery list. Recomputation is automatic on every change
(delete-and-rebuild). Translating totals into purchasable packages (`purchase_qty`) is
deferred to Phase 4, when real Kroger package sizes are available.

## Goals

- Maintain one active draft grocery list; add/remove recipes and set per-recipe target servings.
- Scale each recipe's ingredient quantities by `target_servings / recipe.default_servings`.
- Merge identical canonical ingredients across recipes and sum quantities with `pint`.
- Keep incompatible units as separate sub-quantities on one line; never fabricate a wrong total.
- Carry through unknown quantities (`qty` null → "as needed").
- Auto-recompute the consolidated list on every membership/servings change (idempotent rebuild).
- Present the list grouped by ingredient category for shopping-friendly order.

## Non-Goals (deferred)

- `purchase_qty` / total→packages translation (Phase 4, needs Kroger package sizes).
- Any Kroger product matching or cart concerns (Phase 4).
- "Still have it?" pantry logic (Phase 5).
- Multiple named lists (schema supports it; v1 uses a single draft).
- Manually adding ad-hoc non-recipe items to the list.

## Key Design Decisions (from brainstorming)

1. **Consolidated totals only.** Phase 3 produces accurate totals per ingredient; `purchase_qty`
   stays at its default until Phase 4 supplies package sizes.
2. **Per-recipe target servings, scale by ratio.** `factor = target_servings /
   recipe.default_servings`, defaulting target to the recipe's own `default_servings` (×1).
3. **Incompatible units kept separate.** One canonical-ingredient line may carry several
   `{qty, unit}` sub-quantities.
4. **One active draft list,** built up incrementally; sending to Kroger (Phase 4) flips status
   and a fresh draft starts.
5. **Auto-recompute on every change** via delete-and-rebuild (idempotent, always-correct).

## Data Model & Migrations

Phase 3 adds two schema changes (two Alembic migrations on top of the current head):

**1. `grocery_list_recipes` (new table)** — which recipes (+ target servings) are on a list:

```
grocery_list_recipes
  id, list_id → grocery_lists (CASCADE)
  recipe_id → recipes (CASCADE)
  servings (int)
  UNIQUE (list_id, recipe_id)
```

**2. `quantities` JSONB column on `grocery_list_items`** — multiple consolidated sub-quantities
per ingredient:

```
grocery_list_items   (EXISTING table + new column)
  ...existing columns (list_id, ingredient_id, total_qty, total_unit, purchase_qty,
     kroger_upc, source_recipe_ids, pantry_status)...
  quantities (JSONB, default [])   -- [{"qty": 3.0, "unit": "cup"}, {"qty": 2.0, "unit": "clove"}]
```

- `quantities` is the source of truth for display (length 1 in the common single-unit case).
- `total_qty` / `total_unit` are kept and populated ONLY when `len(quantities) == 1` (else null),
  as a convenience scalar for Phase 4 product matching's simple case.
- `source_recipe_ids` (already present) records which recipes contributed the line.
- `pantry_status` defaults `"needed"` (Phase 5 fills the rest).

**Why JSONB over a child table:** sub-quantities are always read/written with their item, never
queried independently, and are usually length 1 — a join would add cost for no benefit.

**Draft-list singleton:** the active draft = the `grocery_lists` row with `status="draft"`. The
service ensures exactly one exists (creates on first use). Phase 4's send flips it to
`sent_to_kroger`; the next add creates a fresh draft.

## Architecture

New backend package `app/consolidate/`. The pure unit math is isolated from DB/IO so it is
exhaustively testable; the service owns all writes; the router is thin.

```
backend/app/consolidate/
├── __init__.py
├── units.py        pure pint-wrapped consolidation core (no DB, no network)
├── schemas.py      Pydantic request/response models
├── service.py      draft-list singleton + delete-and-rebuild; only writer of
│                   grocery_list_recipes & grocery_list_items
└── router.py       draft-list endpoints; registered in app/main.py
```

`pint` (already a transitive dependency via `ingredient-parser-nlp`) is wrapped entirely inside
`units.py`; nothing else imports it.

## Consolidation Logic (delete-and-rebuild)

On any change to the draft list's membership or servings, the service rebuilds the list's items
from scratch:

1. **Scale.** For each `grocery_list_recipes(recipe, servings)`: `factor = servings /
   recipe.default_servings`; for each `recipe_ingredient`, `scaled_qty = qty * factor` (`qty`
   null stays null). Yields `(ingredient_id, scaled_qty, unit, recipe_id)`.
2. **Group** all scaled lines by `ingredient_id`.
3. **Consolidate units** (per ingredient) via `units.consolidate(list_of_(qty, unit))`:
   - Normalize a small fixed set of cooking unit aliases (e.g. `tbsp`/`T`→`tablespoon`,
     `c`→`cup`, `tsp`→`teaspoon`) before handing to `pint`.
   - Units `pint` knows join a dimension group (volume / mass / …); within a compatible group,
     convert all to the FIRST-seen unit and sum.
   - Units `pint` can't parse ("clove", "pinch", "can", "stick") each form their own group keyed
     by the exact (normalized) unit string, summed within that string.
   - `unit` null → a dimensionless count group (e.g. eggs).
   - `qty` null → a sub-quantity with `qty: null` (display "as needed").
   - Round summed quantities to 3 decimals to avoid float-accumulation noise.
   - Returns `quantities = [{qty, unit}, ...]`.
4. **Write.** One `grocery_list_items` row per ingredient: `quantities`, `source_recipe_ids`,
   `total_qty`/`total_unit` set only when `len(quantities)==1` else null, `pantry_status`
   `"needed"`.

**Worked example** — Pancakes (×1.5) + Bread (×1):
- flour: `2 cups`×1.5 + `240 ml`×1 → both volume → 3 cups + 240 ml-as-cups ≈ `4.01 cups`.
- eggs: `2`×1.5 + `1`×1 → count → `4`.
- garlic: `2 cloves`×1.5 + `1 tbsp`×1 → unconvertible → `3 cloves + 1 tbsp` (two sub-quantities).

## API

New router registered in `main.py`. Every mutation recomputes and returns the fresh list.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/list` | Current draft list (member recipes + consolidated items). Creates an empty draft if none exists. |
| `POST` | `/list/recipes` | Body `{recipe_id, servings?}` (defaults to recipe's `default_servings`). Adds recipe (upsert on duplicate), recomputes. |
| `PATCH` | `/list/recipes/{recipe_id}` | Body `{servings}`. Updates target servings, recomputes. 404 if not on list. |
| `DELETE` | `/list/recipes/{recipe_id}` | Removes recipe, recomputes. 404 if not on list. |

`ListRead` response: `{id, status, recipes: [{recipe_id, title, servings, default_servings}],
items: [{ingredient_id, ingredient_name, category, quantities: [{qty, unit}], source_recipe_ids,
pantry_status}]}`. Items grouped/sorted by `category`.

## Frontend

Reuses the Phase 2 recipe library; adds one screen and one action.

- **"Add to list" action** on the recipe list/detail screens (with an optional servings input)
  → `POST /list/recipes`.
- **New "Grocery List" screen** in app nav (alongside "Recipes" / "Add recipe"): shows member
  recipes (each with an editable servings field + remove button) and, below, the consolidated
  items grouped by category, each line showing the ingredient name and its quantities (e.g.
  "garlic — 3 cloves + 1 tbsp"). Editing servings or removing a recipe re-fetches the recomputed
  list. Empty state when no recipes are added.
- `api.ts` gains `getList`, `addRecipeToList`, `updateListServings`, `removeRecipeFromList`;
  `types.ts` gains the list types.

## Error Handling

Governing principle: **consolidation never fabricates a wrong number** — separate when it can't
combine, say "as needed" when a quantity is unknown.

| Situation | Handling |
|---|---|
| `qty` null ("salt to taste") | Sub-quantity with `qty: null` ("as needed"); never treated as 0 or dropped. |
| `pint` can't parse a unit | Expected — own string-keyed sub-quantity group (the mechanism, not a failure). |
| Incompatible units for one ingredient | Multiple sub-quantities on the line; no fabricated total. |
| `default_servings` 0/null | Guard the factor: treat missing/zero as 1 (no divide-by-zero). |
| Adding a recipe already on the list | `(list_id, recipe_id)` unique → upsert servings, no duplicate/error. |
| PATCH/DELETE for a recipe not on the list | 404. |
| Recipe with zero parseable ingredients | Added fine; contributes nothing (empty is valid). |
| Float accumulation noise | Round summed quantities to 3 decimals. |

## Testing Strategy

No LLM is involved in Phase 3 (consolidation is pure math), so nothing to mock there.

- **`units.py`** — pure table-driven unit tests: same-unit sum; cross-unit compatible sum
  (cups+ml→cups, g+oz→g); incompatible units kept separate; count items; unit-alias
  normalization; `qty=None` carried through; float rounding. The correctness-critical core,
  exhaustively covered. No DB.
- **`service.py`** — DB-backed (`db_session` fixture): scaling by servings ratio; grouping across
  recipes by canonical ingredient; delete-and-rebuild idempotency (recompute twice → identical);
  `source_recipe_ids` populated; draft singleton creation; `total_qty`/`total_unit` set only for
  single-unit items.
- **`router.py`** — FastAPI TestClient: GET creates/returns draft; add/patch/remove return the
  recomputed list; upsert-on-duplicate; 404s.
- **Frontend** — Vitest/Testing-Library for the Grocery List screen (member recipes + grouped
  items, edit-servings re-fetch, empty state) and the "Add to list" action, with `fetch` mocked.

## Dependencies

- `pint` is already available transitively via `ingredient-parser-nlp` (2.7.0). To make the direct
  dependency explicit (Phase 3 imports `pint` directly in `units.py`), add `pint` to
  `backend/pyproject.toml` dependencies and update `uv.lock` — consistent with the Phase 2
  `requests`-explicit decision.
- No new frontend dependencies expected.

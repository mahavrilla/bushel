# Bushel Phase 2 — Recipes & Parsing Design Spec

**Date:** 2026-06-19
**Status:** Approved design, pending implementation plan
**Builds on:** Phase 1 Foundation (FastAPI + Postgres + React skeleton, full 8-table schema, Docker Compose). See `2026-06-19-bushel-design.md` for the overall product design.

## Summary

Phase 2 builds the recipe-import and ingredient-parsing subsystem. It lets the user import a
recipe by URL (via the `recipe-scrapers` library, with a Claude fallback for unsupported sites)
or by manual entry, parses each ingredient line into `{qty, unit, name}` (via the
`ingredient-parser` library, with a Claude fallback for messy lines), and resolves each parsed
line to a canonical, deduplicated `Ingredient` (deterministic normalize + alias lookup, with
Claude only for genuinely new ingredients). Low-confidence or new results are flagged for human
review in a small React UI. Import is synchronous.

This phase only populates existing tables (`recipes`, `recipe_ingredients`, `ingredients`); it
introduces the first real API router and the `llm/` integration.

## Goals

- Import a recipe by URL: scrape title, servings, and raw ingredient lines.
- Manual entry: title + servings + raw ingredient lines (one textarea), through the same parser.
- Parse each raw line into `{qty, unit, name}` with a confidence and a recorded source.
- Resolve each parsed line to a canonical `Ingredient` (existing via normalize+alias, or new).
- When creating a new ingredient, capture `category` and `default_purchase_unit` too.
- Flag lines needing review; provide a UI to review and correct them.
- Never hard-fail an import on parse quality — worst case, flag for review.

## Non-Goals (deferred)

- Servings *scaling* and quantity consolidation (Phase 3).
- Any Kroger/product matching or cart concerns (Phase 4+).
- Recipe deletion, title editing, tags, photos.
- Raw-text-paste import from arbitrary sources beyond the manual textarea.
- Camera/OCR import (post-MVP).
- Async/job-queue import (synchronous is sufficient for a single user).

## Key Design Decisions (from brainstorming)

1. **Canonicalization:** normalize (lowercase/trim/singularize) + match against
   `Ingredient.canonical_name` and `aliases`; on a miss, ask Claude to classify the unknown
   against the existing canonical set — alias to an existing ingredient, or create a new one.
   Deterministic for known ingredients; Claude only for genuinely new ones.
2. **Parsing:** library-first (`ingredient-parser`); Claude fallback only on failure/low
   confidence. `parse_source` records `library` | `llm` | `manual`.
3. **Import flow:** synchronous request with a frontend loading state. No job queue.
4. **Manual entry:** title + servings + a textarea of raw lines, run through the *same*
   parse→canonicalize pipeline. One code path.
5. **New ingredient metadata:** the same LLM call that confirms "new" also returns `category`
   and a sensible `default_purchase_unit`, populating those `Ingredient` fields immediately so
   Phase 3 (total→packages) and list grouping work without backfill.

## Architecture

Phase 2 adds the first API router and four focused backend modules. Fuzzy logic (scraping, ML
parsing, LLM) is isolated behind small interfaces; deterministic logic (string normalization,
DB writes) is directly unit-testable.

```
backend/app/
├── recipes/
│   ├── router.py        FastAPI routes: import-url, manual, get, list, patch-ingredient
│   ├── service.py       orchestrates: fetch → parse lines → canonicalize → persist
│   ├── scraper.py       URL → {title, servings, raw ingredient lines} (recipe-scrapers; Claude fallback)
│   └── schemas.py       Pydantic request/response models
├── ingredients/
│   ├── parser.py        one raw line → {qty, unit, name, confidence, source} (ingredient-parser; Claude fallback)
│   ├── canonicalize.py  normalized name + alias lookup → existing/new Ingredient (Claude only for new)
│   └── normalize.py     pure string normalization (lowercase, trim, singularize)
└── llm/
    └── client.py        thin Claude wrapper (structured extraction); reused by scraper, parser, canonicalize
```

### Module responsibilities

- **`llm/client.py`** — the single Anthropic integration point. Exposes typed methods
  (`parse_ingredient_line`, `canonicalize_ingredients`, `scrape_recipe`) returning structured
  data. Uses a fast model (Claude Haiku 4.5, id `claude-haiku-4-5-20251001`) for these
  structured-extraction tasks; the model id is configurable via settings. Depends only on
  `config` (API key). The ONLY file that talks to Anthropic. When `ANTHROPIC_API_KEY` is unset,
  its methods raise a recognizable "LLM unavailable" error that callers degrade around.
- **`ingredients/normalize.py`** — pure functions, no dependencies: lowercase, trim collapse
  whitespace, strip trailing descriptors handled by the parser already, singularize. The
  deterministic core of dedup.
- **`ingredients/parser.py`** — wraps `ingredient-parser`. Returns
  `{qty: float|None, unit: str|None, name: str, confidence: float, source: "library"|"llm"}`.
  On library failure or confidence below threshold, calls `llm/client.parse_ingredient_line`
  and sets `source="llm"`.
- **`ingredients/canonicalize.py`** — given parsed names for a recipe: normalize each, look up
  against `canonical_name` + `aliases`. Collect misses and resolve them in ONE batched
  `llm/client.canonicalize_ingredients` call that returns, per unknown, either
  `{alias_of: <existing_id>}` or `{new: {canonical_name, category, default_purchase_unit}}`.
  Applies results: adds aliases to existing rows, or creates new `Ingredient` rows.
- **`recipes/scraper.py`** — wraps `recipe-scrapers`. On unsupported site, falls back to
  `llm/client.scrape_recipe` on the fetched HTML. Returns `{title, servings, raw_lines}`.
- **`recipes/service.py`** — orchestrator: scraper → parser (per line) → canonicalize (batched)
  → persist. The one place that writes `Recipe` + `RecipeIngredient` rows and sets flags.
- **`recipes/router.py`** — thin HTTP layer; delegates to service. Registered in `main.py`.

## Data Flow (per recipe)

1. **Acquire raw lines.** URL → `scraper` (recipe-scrapers, Claude fallback) → `{title,
   servings, raw_lines}`. Manual → taken directly from request body.
2. **Parse each line** (`parser`): `ingredient-parser` → `{qty, unit, name, confidence}`;
   low-confidence/failure → Claude fallback. Record `parse_source`.
3. **Canonicalize** (`canonicalize`): normalize names, look up existing; batch the misses into
   one Claude classification call → alias existing or create new (with category +
   default_purchase_unit).
4. **Persist** (`service`): one `Recipe` row + a `RecipeIngredient` per line with `raw_text`,
   `qty`, `unit`, `ingredient_id`, `parse_source`, `needs_review`.

**`needs_review` is set true when:** the parser fell back to Claude with low confidence, OR
`qty`/`unit` could not be parsed, OR canonicalization created a new ingredient, OR
canonicalization was low-confidence.

## Schema Change

One additive migration: add `needs_review BOOLEAN NOT NULL DEFAULT false` to `recipe_ingredients`
(new Alembic revision on top of the Phase 1 initial migration). `parse_source` already exists.
No other schema changes; all other columns already exist from Phase 1.

## API

New router registered in `main.py`. Both creation endpoints return an identical `RecipeRead`
shape so the frontend has one rendering path.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/recipes/import` | Body `{url}`. Scrape → parse → canonicalize → persist. Returns `RecipeRead`. Synchronous. |
| `POST` | `/recipes` | Body `{title, servings, raw_lines: [str]}` (manual). Same pipeline on the raw lines. Returns `RecipeRead`. |
| `GET` | `/recipes/{id}` | Recipe + ingredients (with `needs_review`). |
| `GET` | `/recipes` | List recipes (id, title, servings) for the library view. |
| `PATCH` | `/recipes/{id}/ingredients/{ing_id}` | Edit qty/unit/name and/or re-link to a different canonical ingredient; clears `needs_review`. |

`RecipeRead` = `{id, title, servings, source_url, ingredients: [{id, raw_text, qty, unit,
ingredient_id, ingredient_name, parse_source, needs_review}]}`.

## Frontend (React)

Three small screens; `api.ts` remains the sole owner of endpoints (new typed functions:
`importRecipe`, `createRecipe`, `getRecipe`, `listRecipes`, `updateIngredient`).

- **Add Recipe** — a URL field OR a manual textarea (title + servings + raw lines), with a
  loading state during the synchronous import; on success routes to the detail view.
- **Recipe detail / review** — each ingredient row shows parsed qty/unit/name and the linked
  canonical ingredient; rows with `needs_review` are highlighted; an "N items need review"
  banner. Each row is inline-editable, calling `PATCH`; saving clears the flag.
- **Recipe list** — the library of imported recipes; entry to detail. (Becomes Phase 3's
  selection surface.)

## Error Handling

The governing principle: **an import never hard-fails on parse quality.** Worst case, lines are
flagged for review. Hard failures are limited to "couldn't get the recipe at all" or invalid
manual input.

| Failure | Handling |
|---|---|
| URL unsupported by recipe-scrapers | Fall back to `llm/client.scrape_recipe` on fetched HTML. If still unusable, return a structured error suggesting manual entry; persist nothing. |
| URL fetch fails (404/timeout/blocked) | Return 422 with the reason; persist nothing. |
| Line won't parse (library fails and LLM low-confidence) | Persist row with `qty/unit=null`, `raw_text` intact, `needs_review=true`. Import succeeds. Never drop a line. |
| Claude unavailable / API error | Parsing degrades to library-only (unparseable lines flagged). Canonicalization degrades to normalized-exact-match only; misses create a new flagged ingredient rather than block. Import always completes. |
| Canonicalization ambiguity / low confidence | Default to creating a new ingredient and flag it (human merges later). Safer than a wrong auto-merge. |
| Duplicate `canonical_name` race | `canonical_name` is unique; on conflict, fetch and reuse the existing row. |
| Malformed manual input | Validate at schema layer; skip blank lines; reject empty title with 422. |

## Testing Strategy

A real Anthropic call is NEVER made in the automated suite — `llm/client` is mocked everywhere.
Tests stay fast, free, deterministic. A live smoke test is a separate, human-run step.

- **`normalize.py`** — pure unit tests over tricky names (plurals, punctuation, casing).
- **`parser.py`** — labeled real ingredient lines; LLM fallback mocked. Assert fallback fires
  only on low-confidence/failure and its result maps correctly; `source` recorded right.
- **`canonicalize.py`** — seeded `ingredients` table: exact hit, alias hit, miss→new (LLM
  mocked), miss→alias-existing (LLM mocked). Verify new ingredients get category +
  default_purchase_unit; verify batching (one call for multiple misses).
- **`scraper.py`** — saved HTML fixtures for a supported and an unsupported site (Claude
  fallback path mocked).
- **`service.py`** — integration test, externals mocked: an import writes correct `Recipe` +
  `RecipeIngredient` rows with correct `needs_review`/`parse_source`.
- **`router.py`** — FastAPI TestClient against the DB fixture, externals mocked: import, manual
  create, get, list, patch-clears-flag.
- **Frontend** — Vitest/Testing-Library for the three screens with `fetch` mocked: loading
  state, review-flag highlighting, inline edit calls PATCH and clears the flag.

## Dependencies Added

- Backend: `recipe-scrapers`, `ingredient-parser`, `anthropic` (Claude SDK). Added to
  `backend/pyproject.toml`; `uv.lock` updated.
- No new frontend dependencies expected.

# Bushel — Design Spec

**Date:** 2026-06-19
**Status:** Approved design, pending implementation plan

## Summary

Bushel is a personal (single-user) web app that turns recipes into a consolidated grocery
list and pushes it into a Kroger cart. It merges duplicate ingredients across recipes, sums
and unit-converts their quantities, translates totals into purchasable packages, and uses a
self-tracked purchase history to ask "you bought this recently — do you still have it?"
before adding items. Recipe import is by URL or manual entry, assisted by an LLM. The app is
API-first so a future iOS client (with camera-based receipt/pantry scanning) reuses the same
backend.

## Goals (MVP)

- Import recipes by URL (structured scrape, LLM fallback) and by manual entry form.
- Parse ingredient lines into `{qty, unit, name}` and resolve them to canonical ingredients.
- Consolidate selected recipes into one grocery list: merge same ingredients, sum quantities
  with unit conversion, and translate totals into purchase quantities (packages).
- Maintain a self-tracked purchase log and prompt "still have it?" for recently bought items.
- Match each ingredient to a specific Kroger product — confirm once, remember forever.
- Push the finished list to the user's Kroger cart and record what was sent.

## Non-Goals (explicitly out of scope for MVP)

- iOS app and camera/receipt/pantry photo OCR (post-MVP; the `llm/` module is built to extend
  into it).
- Raw-text paste import (URL + manual only for v1).
- Multi-user accounts or sharing (single user).
- Meal-planning calendars, nutrition tracking, budgeting analytics.
- Order placement / checkout — Kroger's API cannot do this; the app hands off to the Kroger
  app/site for checkout and pickup/delivery slot selection.
- Non-Kroger stores.

## Kroger API constraints (verified)

These shaped the design and must be respected:

- **Products API** (`GET /v1/products`): search by term or product ID; paginated via
  `filter.limit` / `filter.start`; fuzzy (result order varies between calls). Price,
  fulfillment type (instore/curbside/delivery/shiptohome), aisle location, and `stockLevel`
  (HIGH / LOW / TEMPORARILY_OUT_OF_STOCK) are returned **only** when `filter.locationId` is
  supplied. App-only auth (client credentials). 10,000 calls/day.
- **Locations API**: find stores by zip/radius; app-only auth. ~1,600 calls/day per endpoint.
- **Cart API**: add items to the user's cart (`cart.basic:write`, user OAuth code flow); takes
  UPC + quantity + modality (PICKUP/DELIVERY). **Write-only — cart contents cannot be read
  back.** ~5,000 calls/day.
- **No order/purchase history API exists.** Therefore "did we buy this recently" must be
  answered from Bushel's own `purchase_log`, written when a list is sent to Kroger.

## Stack

- **Backend:** FastAPI (Python). Chosen for best-in-class libraries for the two hardest
  problems: `recipe-scrapers` (recipe-site scraping), `ingredient-parser` (ingredient-line
  parsing), `pint` (unit conversion). Claude (LLM) is integrated as a first-class fallback for
  messy sites/text and reserved for future receipt/pantry OCR.
- **Frontend:** React (TypeScript) web app.
- **Database:** Postgres (kept even locally, so cloud/home-server migration later is a config
  change, not a rewrite).
- **Deployment:** local via Docker Compose for the POC.

## Architecture

API-first. React talks to FastAPI over JSON/HTTPS. The backend is split into focused modules,
each with one responsibility. The key boundary: **everything fuzzy (parsing, matching, pantry
guesses) is isolated from everything deterministic (consolidation math, Kroger calls).**

```
┌──────────────────────────────────────────────────────────┐
│  React web app  (recipes, list builder, cart review)      │
└───────────────────────────┬──────────────────────────────┘
                            │  JSON over HTTPS
┌───────────────────────────▼──────────────────────────────┐
│  FastAPI                                                   │
│                                                            │
│  recipes/      import (URL+manual), LLM-assisted parsing   │
│  ingredients/  normalize names, parse "2 cups flour"       │
│  consolidate/  merge dup ingredients, sum + convert units  │
│  pantry/       purchase log + "still have it?" logic       │
│  matching/     ingredient → Kroger product, remembered map │
│  kroger/       OAuth tokens, product search, cart push     │
│  llm/          Claude client (parse fallback, future OCR)  │
└───────────────────────────┬──────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
      ┌───────▼────────┐        ┌─────────▼─────────┐
      │  Postgres      │        │  Kroger Public API │
      │  (your data)   │        │  Products/Locations│
      └────────────────┘        │  /Cart             │
                                └────────────────────┘
```

### Modules

- **`recipes/`** — Import a recipe by URL (`recipe-scrapers`; Claude fallback when a site has
  no structured data) or by manual form. Stores recipes with their ingredient lines.
- **`ingredients/`** — Turns a raw line ("2 cups all-purpose flour") into `{qty, unit, name}`
  via `ingredient-parser`, Claude as fallback. Normalizes names so aliases collapse to one
  canonical ingredient.
- **`consolidate/`** — Given selected recipes (+ servings), merges identical ingredients across
  recipes and sums quantities, converting units with `pint`. Produces the working grocery list
  and the total → purchase-quantity translation. **Deterministic; no LLM.**
- **`pantry/`** — Maintains the self-tracked purchase log; flags recently bought items and
  surfaces "still have it?" prompts.
- **`matching/`** — Maps each canonical ingredient to a specific Kroger product. First time:
  show search results, user picks, remember it (personal ingredient→UPC map). Known items
  resolve silently.
- **`kroger/`** — Owns Kroger OAuth tokens (storage + refresh), product/location search, and
  the cart push.
- **`llm/`** — Thin Claude client used by `recipes`/`ingredients` now; reserved for
  receipt/pantry photo OCR post-MVP.

## Data model (Postgres)

Single user, so no `users` table for MVP (noted where multi-user would slot in later).

```
recipes
  id, title, source_url, default_servings, created_at

recipe_ingredients          -- raw + parsed lines from a recipe
  id, recipe_id → recipes
  raw_text                  -- "2 cups all-purpose flour, sifted"
  qty, unit                 -- 2, "cup"  (parsed; nullable if unparseable)
  ingredient_id → ingredients
  parse_source              -- "library" | "llm" | "manual"

ingredients                 -- canonical, deduped vocabulary (the hub)
  id, canonical_name        -- "all-purpose flour"
  aliases (text[])          -- ["AP flour", "plain flour"]
  category                  -- "baking", "produce" … (for list grouping)
  default_purchase_unit     -- how you buy it: "bag", "lb" …

ingredient_product_map      -- "confirm once, remember forever"
  ingredient_id → ingredients
  kroger_upc, kroger_description, package_size
  is_default
  last_confirmed_at

grocery_lists               -- one per shopping trip
  id, name, status          -- "draft" | "sent_to_kroger"
  store_location_id         -- chosen Kroger store
  created_at, sent_at

grocery_list_items          -- consolidated line on a list
  id, list_id → grocery_lists
  ingredient_id → ingredients
  total_qty, total_unit     -- summed & unit-converted (what recipes need)
  purchase_qty              -- # of packages to actually buy (e.g. 1 bag)
  kroger_upc                -- resolved product
  source_recipe_ids (int[]) -- which recipes contributed (traceability)
  pantry_status             -- "needed" | "maybe_have" | "skipped"

purchase_log                -- self-tracked history → powers pantry smarts
  id, ingredient_id → ingredients
  kroger_upc, qty, unit
  purchased_at              -- when this list was sent to Kroger
  source_list_id → grocery_lists

kroger_auth                 -- single row: Kroger OAuth tokens
  access_token, refresh_token, expires_at, scopes
```

**Deliberate decisions:**

1. `ingredients` is the hub — recipes, product map, list items, and purchase history all point
   at canonical ingredients, so "flour" means the same thing everywhere and the remembered
   Kroger pick + history follow the ingredient, not the recipe.
2. `grocery_list_items` keeps both `total_qty` (what recipes need) and `purchase_qty` (packages
   to buy) — the consolidation→purchasable translation made explicit.
3. `purchase_log` is append-only, written when a list is sent to Kroger. It is the only source
   of "did we buy this recently." Post-MVP receipt scanning writes corrected rows here too.
4. `source_recipe_ids` lets the UI show "this 3 cups flour comes from Pancakes + Bread."

## End-to-end flow

**Setup (one-time):**

1. Connect Kroger account (OAuth code flow → store tokens in `kroger_auth`). Redirect URI
   `http://localhost:<port>/auth/callback`, registered in the Kroger app config.
2. Pick home store (Locations API search by zip → `store_location_id`). Required because
   price/stock/aisle are per-store.

**Building a trip:**

1. **Add recipes.** URL → `recipe-scrapers`; if no structured data, Claude parses the page.
   Manual → form. Each ingredient line → `ingredients/` parses `{qty, unit, name}` and resolves
   to a canonical ingredient (or creates one). Low-confidence parses are flagged for review.
2. **Choose what to cook.** Select recipes for this trip, set servings each (scales quantities).
3. **Consolidate** *(deterministic)*. Merge same ingredient across recipes, sum quantities with
   `pint` unit conversion, translate total → `purchase_qty` using `default_purchase_unit`
   (e.g. "3 cups flour total → buy 1 bag (5 lb)").
4. **Pantry check.** For each item, inspect `purchase_log`; flag recently bought items
   `maybe_have` and prompt "2 lb rice bought 6 days ago — still have it?". User answers per item
   → keep (`needed`) or drop (`skipped`).
5. **Match to products.** For each kept item, check `ingredient_product_map`: mapped → use
   remembered UPC silently; unmapped/ambiguous → Products API search (with `locationId`), user
   picks, remember it. Show `stockLevel`; warn on `TEMPORARILY_OUT_OF_STOCK`.
6. **Review & send.** Show final list (product, package, qty, price, aisle, est. total). User
   confirms → Cart API pushes items (UPC + qty + modality). Write `purchase_log` rows for
   successfully pushed items, mark list `sent_to_kroger`. User finishes in the Kroger app/site
   (checkout, pickup/delivery slot).

The cart push is the end of Bushel's job; checkout/slot selection happens in Kroger's app.

## Error handling

| Failure | Handling |
|---|---|
| Recipe URL won't scrape | Fall back to Claude; if low-confidence, open the manual form pre-filled with what was extracted. Never silently lose a recipe. |
| Ingredient line unparseable | Flag for review with raw text editable; do not guess. |
| Unit can't be converted (e.g. "2 cloves" + "1 tbsp" garlic) | Do not fake-merge incompatible units; keep separate sub-quantities and show both rather than produce a wrong total. |
| No good Kroger product match | Show search results; allow manual search or mark item "buy in person" (stays on list, not pushed). |
| Kroger token expired | Auto-refresh; if refresh fails, prompt re-auth before any cart push. |
| Cart push partially fails | Tolerant per-item push; report success/failure; log only successfully pushed items to `purchase_log` so history stays truthful. |
| Item out of stock | Warn at review (from `stockLevel`); allow keep, swap, or skip. |
| Kroger rate limit hit | Cache product/location lookups; respect daily caps; surface a clear "try later" rather than crash. |

## Testing strategy

- **Consolidation + unit math** (`consolidate/`, `pint`): pure table-driven unit tests over
  messy real recipe combos. This is the correctness-critical core. No network.
- **Parsing** (`recipes/`, `ingredients/`): tests against saved recipe-page fixtures and a
  labeled set of ingredient lines; LLM mocked in CI.
- **Kroger client** (`kroger/`): tests against recorded API responses (fixtures), plus a thin
  live smoke test run manually against the sandbox.
- **Matching + pantry logic**: unit tests over seeded `ingredient_product_map` / `purchase_log`.
- **End-to-end happy path**: recipes → list → consolidated → matched → (mocked) cart push.

## Deployment (local, Docker Compose)

```
docker compose up
├── db    → Postgres (named volume for persistence)
├── api   → FastAPI (the backend modules above)
└── web   → React build served by nginx (Vite dev server in dev)
```

- `.env` holds Kroger client ID/secret, Claude API key, and the Postgres connection string.
- Local-only access for the POC (`localhost`). API-first, so exposing the `api` container later
  (e.g. via Tailscale or a small host) enables phone/iOS access with no code changes.
- OAuth redirect URI: `http://localhost:<port>/auth/callback`.

## Future (post-MVP)

- iOS client reusing the same FastAPI backend.
- Camera-based receipt scanning (LLM vision) → corrected `purchase_log` rows for accurate
  pantry tracking without manual confirmation.
- Pantry photo scanning to seed/update on-hand inventory.
- Optional raw-text paste import.

# Bushel — Home Store Persistence + Saved Staples (design)

**Date:** 2026-06-21
**Status:** approved (pre-implementation)
**Depends on:** Phases 1–6 (complete). Post-MVP enhancement, not a numbered phase.

## Goal

Two independent state-persistence improvements raised together:

- **A — Home store as a user setting.** The chosen Kroger store currently lives on the draft
  grocery list, so every new draft (after sending a cart, or a fresh one) loses it and forces a
  re-pick. Persist it once at the app/user level so it applies to every trip.
- **B — Saved staples.** Add items that aren't from a recipe (staples like peanut butter) to a
  trip, from a reusable saved catalog. Each staple can auto-add to every trip (toggleable). The
  chosen Kroger product (UPC) is remembered per ingredient — which the existing
  `ingredient_product_map` + silent reuse already provide for free.

Backend-heavy; no new Kroger/LLM calls beyond the existing `canonicalize` path for a brand-new
staple name. Frontend reuses the Phase 6 Warm Pantry primitives.

The two parts are independent and can be built/merged in sequence (A first, then B).

---

## Part A — Home store as a user setting

### Problem

`grocery_lists.store_location_id` is per-draft. `matching.set_store` writes it to the draft;
`get_match_state` / `search_item_products` / `send_to_cart` read it from the draft. So a new draft
(created after a list is sent, or on a fresh start) has no store → the user must re-pick. Also the
UI shows the raw id ("L1").

### Schema — one new table

```
app_settings                 -- single row (single-user app)
  id                         INTEGER PK
  home_store_location_id     VARCHAR(50)  NULL
  home_store_name            VARCHAR(255) NULL
```

A single-row settings table (cleaner than overloading `kroger_auth`; a home for future prefs).

### Behavior

- **`app/settings/` module** (`service.py`, `schemas.py`): `get_settings_row(db)` returns/creates
  the single row; `set_home_store(db, location_id, name)` upserts it.
- **`matching.set_store(db, location_id, name)`** now writes the home store via the settings
  service instead of the draft. It still returns `MatchRead`.
- **Matching reads the home store from `app_settings`**: `get_match_state` reports
  `store_location_id` from settings; `search_item_products` and `send_to_cart` use the settings
  home store (raise `NoStoreSelectedError` when unset, as today).
- `grocery_lists.store_location_id` becomes vestigial — left in place (unused) to avoid a
  destructive migration; reads/writes move to `app_settings`.
- **`SetStoreRequest`** gains `name: str | None`; the frontend sends the store's name (from
  `GET /kroger/locations`) along with the id so the setting stores a human label.

### Frontend

`KrogerSetup` hydrates the home store from the match/settings on mount and shows
"Home store: Kroger Downtown" (name, not id). Picking a store updates the setting; no re-pick after
refresh or after sending a list. The store list's "Use this store" sends both id and name.

---

## Part B — Saved staples

### Schema — two new tables + one column

```
staples                       -- reusable staple catalog (single-user)
  id                INTEGER PK
  ingredient_id     → ingredients (UNIQUE)   -- one staple per canonical ingredient
  auto_add          BOOLEAN NOT NULL DEFAULT true   -- seed onto every new trip when true

grocery_list_staples          -- which staples are on a given draft
  id                INTEGER PK
  list_id           → grocery_lists (CASCADE)
  staple_id         → staples (CASCADE)
  UNIQUE (list_id, staple_id)

grocery_lists.staples_seeded  BOOLEAN NOT NULL DEFAULT false   -- auto-seed runs once per draft
```

### `app/staples/` module (`service.py`, `schemas.py`, `router.py`)

**Catalog management:**
- `add_staple(db, name, llm)` → `canonicalize_names([name], db, llm)` resolves/creates the
  canonical ingredient (new ones get category + `default_purchase_unit` via Claude, same as recipe
  ingredients), then inserts a `staples` row. If a staple already exists for that ingredient, it's
  a no-op (returns the existing one) — no duplicate.
- `remove_staple(db, staple_id)` (deletes catalog row + its trip links via cascade);
  `set_auto_add(db, staple_id, auto_add)`.

**Per-trip sync + links:**
- `sync_draft(db, draft)` — if `draft.staples_seeded` is false, insert a `grocery_list_staples`
  link for every `auto_add` staple and set `staples_seeded = true`. Idempotent afterward, so a
  staple the user removes from a trip stays removed (auto-seed won't re-add it). Called when the
  staples/list view is read (keeps `consolidate/` uncoupled from staples).
- `add_to_trip(db, staple_id)` / `remove_from_trip(db, staple_id)` — insert/delete the link for
  the active draft; both trigger a list recompute.

**View:** `get_view(db)` runs `sync_draft`, returns the catalog with per-staple `ingredient_name`,
`auto_add`, and `on_trip` (whether linked to the active draft).

### `_recompute` change (`consolidate/service.py`)

After gathering recipe-membership quantities into `grouped`, also fold in the draft's linked
staples: for each `grocery_list_staples` row, add a `(None, None)` "as needed" quantity to that
ingredient's group. A staple-only ingredient produces an item with empty `source_recipe_ids`
(i.e. a manual item); a staple ingredient that also appears in a recipe merges into one item
(keeping the recipe's `source_recipe_ids`). Staples thus flow through
consolidation, silent product reuse, and the pantry check exactly like recipe items. `_recompute`
stays deterministic (the staple lookup is a plain DB read; no network/LLM).

> Note: `_recompute` reads `grocery_list_staples` directly (a simple query), keeping the staples
> *logic* in `app/staples/` while the rebuild stays in `consolidate/`. This is the same kind of
> minimal cross-read already used for recipe memberships.

### Endpoints (`staples/router.py`)

- `GET /list/staples` → runs `sync_draft`, returns the catalog view (`StapleView`).
- `POST /staples {name}` → add to catalog (returns the catalog view).
- `DELETE /staples/{staple_id}` → remove from catalog (404 unknown).
- `PATCH /staples/{staple_id} {auto_add}` → toggle auto-add (404 unknown).
- `POST /list/staples/{staple_id}` → add to current trip; `DELETE /list/staples/{staple_id}` →
  remove from current trip (404 unknown). Both recompute the list.

Registered in `app/main.py`.

### Frontend

A **"Staples"** section on the grocery list: the saved catalog as a checklist (checked =
`on_trip`), an "add a staple" text input, and a per-staple auto-add toggle + remove. Toggling a
checkbox calls the on-trip add/remove endpoints; the section reuses the Warm Pantry primitives
(`Card`, `Button`, `Input`, `Pill`). New api.ts functions: `getStaples`, `addStaple`,
`removeStaple`, `setStapleAutoAdd`, `addStapleToTrip`, `removeStapleFromTrip`.

### UPC persistence

Automatic: staple items resolve to canonical ingredients, so the remembered `ingredient_product_map`
gives the same product on every trip, with the per-item "Change" in `MatchAndSend` to re-pick (which
updates the map).

---

## Testing

Backend on the isolated test DB (port 5544, `bushel_test`); LLM (`canonicalize`) and Kroger mocked.

**Part A:**
- `settings.service`: `set_home_store` upserts the single row; `get_settings_row` creates-on-first-read.
- `matching`: `set_store` writes settings; `get_match_state.store_location_id` reflects the setting;
  `search_item_products` uses it; **persists across a newly-created draft** (the bug); unset → `NoStoreSelectedError`.
- Migration creates `app_settings`.
- Frontend: `KrogerSetup` shows the home-store name from settings (hydrated on mount).

**Part B:**
- `staples.service`: `add_staple` canonicalizes + inserts; duplicate ingredient → no second row;
  `remove_staple`/`set_auto_add`; `sync_draft` links auto staples once and is idempotent
  (removed-stays-removed on re-sync); `add_to_trip`/`remove_from_trip` toggle links.
- `_recompute`: a linked staple becomes an item; a staple ingredient also in a recipe merges to one
  line; staples survive a recipe edit.
- `staples/router`: catalog CRUD + on-trip add/remove (404 on unknown), `GET /list/staples` returns
  `on_trip`/`auto_add`.
- Migrations: `staples`, `grocery_list_staples`, `grocery_lists.staples_seeded`.
- Frontend (vitest): Staples section adds/removes/toggles and reflects `on_trip`.

## Out of scope / future

- Removing the now-vestigial `grocery_lists.store_location_id` column (low-value separate migration).
- Per-staple default quantities (staples are "as needed" → `purchase_qty` 1 or computed from the
  product package, like any unquantified item).
- Multi-user settings (single-user app; `app_settings`/`staples` are single-tenant).

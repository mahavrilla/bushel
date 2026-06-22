# Bushel — Phase 5: Matching & Pantry (design)

**Date:** 2026-06-21
**Status:** approved (pre-implementation)
**Depends on:** Phase 4 (Kroger integration — `ingredient_product_map`, `purchase_log`, the match/send flow) and Phase 6 (Warm Pantry UI primitives + routing).
**Note:** This is the last planned phase (Phase 6 was pulled forward before it).

## Goal

Make the grocery→cart flow smart about what you already have and what you've already matched:

1. **Silent product reuse** — once you've confirmed a Kroger product for an ingredient, every
   future trip (and every list rebuild within a trip) auto-resolves it from the remembered map.
   You only pick a product the first time; you can still change any item's product, and the change
   is remembered.
2. **Pantry "still have it?"** — flag ingredients you bought recently (per your self-tracked
   `purchase_log`) so you can skip re-buying them. Decisions are auto-surfaced and persist across
   recipe edits within a trip.

**Backend-heavy; no new external (Kroger/LLM) calls — both features are pure DB logic.** Frontend
additions reuse the Phase 6 primitives.

## Scope (from brainstorming)

- **Pantry heuristic:** a single global "recently bought" window (`pantry_recent_days`, default
  14). You judge each flagged item from the shown purchase info; no per-category windows, no
  quantity heuristic.
- **Pantry trigger/persistence:** flagging is automatic on list view; keep/skip decisions persist
  across recipe edits (per ingredient) and never re-prompt once resolved.
- **Product reuse:** re-derived from the persistent `ingredient_product_map` (not stored on the
  rebuilt row). Every item shows its matched product with a Change action.

Out of scope: per-category pantry windows, quantity-based pantry inference, a settings UI for the
window (it's a config value), receipt/photo pantry scanning (post-MVP), any backend API/Kroger
changes beyond what's listed here.

## Architecture

**New module `app/pantry/`:**
```
app/pantry/
  service.py   # evaluate(db); set_decision(db, item_id, keep); _last_purchase lookup
  schemas.py   # PantryItemRead, PantryView, PantryDecisionRequest
  router.py    # GET /list/pantry, POST /list/items/{item_id}/pantry
```

**`app/matching/service.py` gains** `apply_remembered_products(db)` — re-derives `kroger_upc` +
`purchase_qty` from `ingredient_product_map` for unresolved kept items. Called at the top of
`get_match_state` and `send_to_cart`.

**`app/consolidate/service.py` `_recompute`** gains snapshot/restore of user pantry decisions
(the only pantry concern in `consolidate/`). It stays deterministic — no network/LLM.

**Module boundaries:** `pantry/` owns pantry evaluation + decisions; `matching/` owns product
resolution; `consolidate/` owns list rebuild and merely preserves the two pantry columns. Product
picks are *derived* state (re-applied from the map); pantry decisions are *user* state (preserved).

## Schema

**One migration:** add `grocery_list_items.pantry_resolved BOOLEAN NOT NULL DEFAULT false`.

Everything else already exists: `grocery_list_items.pantry_status`, `ingredient_product_map`
(populated by Phase 4 `confirm_product`), `purchase_log` (written by Phase 4 `send_to_cart`).

**`grocery_list_items` pantry state:**
- `pantry_status`: `needed` (default; will be bought) · `maybe_have` (flagged, awaiting decision —
  **still bought by default**) · `skipped` (you have it; excluded from match/send via the existing
  `_kept_items`).
- `pantry_resolved`: `false` until you keep/skip. Evaluation only flags `needed` + unresolved
  items, so a kept item never re-prompts.

## Config

Add `pantry_recent_days: int = 14` to `app/config.py` (the tunable window; no UI this phase).

## Silent product reuse

`matching.apply_remembered_products(db)`:
1. Active draft; for each kept item (`pantry_status != "skipped"`) with `kroger_upc is None`:
2. Look up the default `ingredient_product_map` row for `ingredient_id`.
3. If found: set `item.kroger_upc`, recompute `purchase_qty`/`purchase_qty_estimated` via
   `matching.purchase.compute_purchase_qty(total_qty, total_unit, mapping.package_size)`.
4. `db.flush()`. Idempotent; already-resolved and unmapped items are left untouched.

Invoked at the top of `get_match_state` (so the match panel shows resolved products) and
`send_to_cart` (so a send right after a recipe edit still has products). `_recompute` does **not**
preserve `kroger_upc` — it's re-derived here. `confirm_product` is unchanged: still the one-time
pick that writes the map; changing a product calls it again and overwrites the default mapping.

## Pantry evaluation & decisions

`pantry.service.evaluate(db)` (idempotent, runs on read):
1. Active draft; for each item with `pantry_resolved == false` AND `pantry_status == "needed"`:
2. Find the most recent `purchase_log` row for `ingredient_id` with
   `purchased_at >= now() − pantry_recent_days days`.
3. If found, set `pantry_status = "maybe_have"` (leaves `pantry_resolved` false). `db.flush()`.

`pantry.service.set_decision(db, item_id, keep)`:
- `keep=True` → `pantry_status="needed"`, `pantry_resolved=True`.
- `keep=False` → `pantry_status="skipped"`, `pantry_resolved=True`.
- Unknown item → `ItemNotFoundError`.

`_recompute` snapshot/restore: before deleting items, capture
`{ingredient_id: (pantry_status, pantry_resolved)}`; after rebuild, restore for ingredients still
on the list. New ingredients start `needed`/unresolved and get flagged on the next `evaluate`.

**No purchase history** → nothing flags; the feature is silent until at least one cart has been
sent. Out-of-window purchases stay `needed`.

## Endpoints

- `GET /list/pantry` → runs `evaluate`, returns `PantryView`: for each draft item,
  `item_id`, `ingredient_name`, `pantry_status`, and for `maybe_have` items the prompt data
  `last_qty`, `last_unit`, `purchased_at`, `days_ago`. (Mutates idempotently — same pattern as
  `get_match_state`.)
- `POST /list/items/{item_id}/pantry` body `{keep: bool}` → `set_decision`, returns the refreshed
  `PantryView`. `404` on unknown item.

Both registered in `app/main.py`. The product-match endpoints (`GET /list/match`,
`/list/items/{id}/products`, `/list/items/{id}/product`, `POST /list/send`) are unchanged except
that `get_match_state`/`send_to_cart` now call `apply_remembered_products` first.

## Frontend (Warm Pantry primitives)

New `api.ts` functions: `getPantry()`, `setPantryDecision(itemId, keep)`. New types `PantryItem`,
`PantryView`.

**Match panel (`MatchAndSend` on `/list`):** each kept item shows its **matched product**
(description + package size from the map) or "No product chosen yet" if unmapped, with a
**Change** button (or **Find product** when unmapped) that opens the existing product search;
choosing a result calls `confirmProduct` (sets the item *and* updates the remembered map). Search
results show live price/stock pills; out-of-stock → danger pill. `purchase_qty` shows the
"check quantity" pill when estimated. (At-rest items show product description + size only — no
per-item live price lookup, to keep Kroger calls bounded.)

**Pantry prompts (grocery list, `/list`):** on load the page calls `GET /list/pantry`;
`maybe_have` items render a prompt — *"Flour — bought 5 lb, 6 days ago. Still have it?"* — with
**Keep** and **I have it** (skip) buttons calling `POST /list/items/{id}/pantry`. Skipped items
move to a muted "Skipping (already have)" group; kept items rejoin the normal list. Unflagged
items render normally.

## Error handling

This phase adds no new Kroger/LLM calls; pantry + silent-reuse are pure DB operations.
- `evaluate`/`apply_remembered_products`: no-ops when there's no history/mapping; `total_qty=None`
  is fine (pantry is time-based, qty is display-only).
- `POST .../pantry` and the change/confirm flow → `404` on unknown item; `maybe_have` defaults to
  *included* so a missed decision never silently drops an item from the cart.
- Frontend pantry/match calls surface failures via `ErrorBanner`; the Phase 4 reauth (409) path
  still applies to the product-change and send calls.

## Testing

Backend against the isolated test DB on port 5544 (`bushel_test`); all Kroger mocked.

- **`pantry/service`** — table-driven: flags a purchase inside the window, not one outside; only
  flags `needed`+unresolved (leaves resolved/skipped/maybe_have-already untouched); `set_decision`
  keep→needed+resolved, skip→skipped+resolved; unknown item raises. Seeded `purchase_log`.
- **`matching.apply_remembered_products`** — resolves `kroger_upc`+`purchase_qty` from a seeded
  `ingredient_product_map`; idempotent; skips already-resolved and unmapped items; verified to run
  via `get_match_state`.
- **`_recompute` snapshot/restore** — `pantry_status`+`pantry_resolved` preserved for ingredients
  still present after a recipe edit; a newly-added ingredient starts `needed`/unresolved.
- **`pantry/router`** — `GET /list/pantry` returns flags + prompt data; `POST .../pantry` keep/skip
  updates state and skipped items drop out of `_kept_items` (and thus match/send).
- **Migration** — `pantry_resolved` defaults `false` on a flushed item.
- **Frontend (vitest, router-wrapped)** — `MatchAndSend` shows each item's matched product + a
  Change action; `getPantry` prompts render "still have it?" and Keep/skip call the API.

## Out of scope / future

- Per-category or per-ingredient pantry windows; quantity-based "still have it" inference.
- A settings screen for `pantry_recent_days` (config-only for now).
- Receipt/pantry photo scanning (post-MVP, would write corrected `purchase_log` rows).

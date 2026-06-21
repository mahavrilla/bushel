# Bushel — Phase 4: Kroger Integration (design)

**Date:** 2026-06-20
**Status:** approved (pre-implementation)
**Depends on:** Phase 3 (consolidation) — reads `grocery_list_items.total_qty/total_unit`.
**Hands off to:** Phase 5 (matching & pantry) extends `matching/` with silent reuse + pantry smarts.

## Goal

Take the consolidated draft grocery list and get it into the user's real Kroger cart:
connect a Kroger account (OAuth), pick a home store, match each list item to a specific Kroger
product (confirm once → remembered), translate consolidated totals into package quantities, and
push the items to the cart (write-only). Record what was actually sent to `purchase_log` so later
phases can answer "did we buy this recently?".

The cart push is the end of Bushel's job — checkout and pickup/delivery slot selection happen in
Kroger's own app/site.

## Scope decisions (from brainstorming)

1. **Persist picks now.** Phase 4 writes the confirmed product to `ingredient_product_map` (the
   "remember forever" map) **and** to `grocery_list_items.kroger_upc`. Phase 5 then only adds
   *silent auto-reuse* + pantry/`purchase_log` "still have it?" smarts on top.
2. **Live integration.** Build against the real Kroger API, configured via env vars. Automated
   tests run entirely on recorded fixtures (no network in CI). One **manual live smoke test**
   verifies the real OAuth + cart push.
3. **Compute `purchase_qty` when possible.** Parse the Kroger product's `package_size` and use
   `pint` to compute `ceil(total_qty / package_size)` when units are compatible; fall back to `1`
   and set a `purchase_qty_estimated` flag when `total_qty` is `None` or units don't convert.
4. **Functional, unpolished UI.** Build working React screens for the full flow in the existing
   Phase 2/3 style; visual refinement is deferred to Phase 6.

### Out of scope (Phase 5+)

- Silent auto-reuse of remembered products without a confirm step.
- Pantry / `purchase_log` "you bought this recently — still have it?" prompts.
- Order placement / checkout / slot selection (not supported by the Kroger API at all).

## Kroger API facts (verified against current docs + Cart API ref PDF, 2026-06-20)

- **Base URL:** `https://api.kroger.com` (production environment).
- **OAuth:** authorization-code flow for customer-scoped calls (cart); client-credentials flow
  for app-only calls (products, locations). Token refresh via `refresh_token`.
- **Scopes:** `product.compact`, `cart.basic:write`, `profile.compact`.
- **Products API** (`GET /v1/products`, app-only, ~10k/day): search by term or id; paginate via
  `filter.limit`/`filter.start`; fuzzy ordering. Price, fulfillment type, aisle, and `stockLevel`
  (HIGH / LOW / TEMPORARILY_OUT_OF_STOCK) returned **only** when `filter.locationId` is supplied.
- **Locations API** (app-only, ~1,600/day per endpoint): find stores by zip/radius → `locationId`.
- **Cart API** (`PUT /v1/cart/add`, customer OAuth, 5,000/day): body
  `{"items":[{"upc","quantity","modality"}]}` where modality ∈ `PICKUP`/`DELIVERY`. **Write-only**
  — cart contents cannot be read back, and the order cannot be placed/checked out via the API.
  Error schemas: `APIError.unauthorized` (401), `APIError.forbidden` (403),
  `APIError.cart.serverError` (5xx), `Invalid.UPC`, `Invalid.modality`, `Invalid.parameters`.

## Architecture

Two new backend modules. `kroger/` is the **only** module that performs network I/O to Kroger; it
never touches the DB. `matching/` is pure app logic + DB and calls into `kroger/` for network and
into `consolidate/units.py` for unit math. This isolates the one untrustworthy boundary (Kroger)
from deterministic logic, mirroring how `consolidate/` is kept pure.

```
backend/app/
  kroger/              ← NEW. Only module that talks to Kroger.
    client.py          httpx calls: token exchange/refresh, locations, products, PUT /v1/cart/add
    auth.py            kroger_auth row read/write; get_valid_token() (auto-refresh)
    schemas.py         typed wrappers over Kroger JSON (TokenResp, Location, Product, CartItem)
    router.py          GET /kroger/status, /kroger/login, /auth/callback, /kroger/locations
  matching/            ← NEW. App logic; depends on kroger/ + consolidate/units.
    purchase.py        (total_qty, total_unit, package_size) → (purchase_qty, estimated)  [pint]
    service.py         per-item match state; confirm pick (persist map + item); send-to-cart
    schemas.py         MatchItem, ProductChoice, ConfirmRequest, SendRequest, SendResult
    router.py          GET /list/match, POST /list/items/{id}/product, POST /list/send
```

Both routers are registered in `app/main.py`. Store location lives on the active draft
(`grocery_lists.store_location_id`, already present). Modality is passed in the `/list/send`
request body (default `PICKUP`) — no persisted column.

## Data & schema

All Kroger tables already exist from Phase 1. Phase 4 **writes**:

- **`ingredient_product_map`** — on confirm, upsert one default product per ingredient:
  `{ingredient_id, kroger_upc, kroger_description, package_size, is_default=true, last_confirmed_at}`.
- **`grocery_list_items.kroger_upc`** — the confirmed product for this trip (null = buy-in-person).
- **`grocery_list_items.purchase_qty`** — computed package count (default `1`).
- **`grocery_lists.store_location_id`** — set when home store is picked.
- **`grocery_lists.status` → `sent_to_kroger`** and **`sent_at`** — on successful send.
- **`purchase_log`** — one append-only row per successfully-pushed item:
  `{ingredient_id, kroger_upc, qty=total_qty, unit=total_unit, purchased_at, source_list_id}`.
- **`kroger_auth`** — single row: `{access_token, refresh_token, expires_at, scopes}`.

**One new Alembic migration** (only schema change): add
`grocery_list_items.purchase_qty_estimated BOOLEAN NOT NULL DEFAULT false`, set `true` when
`purchase_qty` fell back to `1`, so the review UI can flag "please check this quantity."

OAuth CSRF `state` is kept transient in-process (single-user local app), not persisted.

## Configuration

`app/config.py` already stubs `kroger_client_id`, `kroger_client_secret`, and
`kroger_redirect_uri` (default `http://localhost:8000/auth/callback`). Phase 4 consumes these.
The redirect URI must be registered in the Kroger developer app config. No new settings required.

## End-to-end flow & endpoints

### Setup (one-time / occasional)

1. **Connect Kroger.** `GET /kroger/login` → returns Kroger's authorize URL (scopes
   `product.compact cart.basic:write profile.compact`, plus a `state` for CSRF). User authorizes
   → Kroger redirects to `GET /auth/callback?code&state` (path matches the configured
   `kroger_redirect_uri`, registered in the Kroger app; handler lives in `kroger/router.py`) →
   `client.py` exchanges the code for tokens → `auth.py` writes the `kroger_auth` row. `GET /kroger/status` reports
   connected / expired / disconnected.
2. **Pick home store.** `GET /kroger/locations?zip=` (client-credentials token) lists nearby
   stores; user picks one → `PATCH /list` (existing consolidate router) sets `store_location_id`
   on the active draft. Required because price/stock/aisle are per-store.

### Per trip (after consolidation)

3. **Match.** `GET /list/match` returns each kept item with either its mapped product (from
   `ingredient_product_map`, pre-selected) **or** live `kroger/` product search results for the
   canonical name (with `locationId` → price/stock/`stockLevel`), plus the computed `purchase_qty`
   and `purchase_qty_estimated` flag. Optional `?q=` free-text override per item for manual search.
4. **Confirm a product.** `POST /list/items/{id}/product`
   `{kroger_upc, kroger_description, package_size}` → upserts `ingredient_product_map`, sets the
   item's `kroger_upc`, recomputes `purchase_qty`/`purchase_qty_estimated` from the new
   `package_size`. An item with no acceptable match is left as **buy-in-person** (`kroger_upc`
   null → excluded from send, stays on the list).
5. **Send.** `POST /list/send {modality}` → builds the payload from items that have a
   `kroger_upc`; `auth.get_valid_token()` ensures a valid token (auto-refresh; on refresh failure
   → `409 reauth_required`); `client.py` does a **tolerant per-item** `PUT /v1/cart/add`. Writes
   `purchase_log` rows for successes only, marks the list `sent_to_kroger` (if ≥1 item pushed),
   sets `sent_at`, and returns per-item `{upc, ok, error}`. User completes checkout in Kroger's app.

**Why per-item PUT** (not one batched call): the cart is write-only, so per-item calls are the
only way to get truthful per-item success/failure for `purchase_log`. ~N calls/trip is trivial
against the 5,000/day cap.

Token auto-refresh is centralized in `auth.get_valid_token()`. `purchase_qty` recompute reuses
`consolidate/units.py` — no duplicate `pint` logic.

## Error handling

| Failure | Handling |
|---|---|
| No Kroger product match | `/list/match` returns empty results; user does a manual `?q=` search or marks the item buy-in-person (`kroger_upc` null → excluded from send, stays on list). |
| Token expired | `get_valid_token()` auto-refreshes via `refresh_token`. If refresh fails → `409 {error: reauth_required}`; UI prompts reconnect. No cart push proceeds without a valid token. |
| Cart push partially fails | Per-item tolerant push; collect `{upc, ok, error}`. `purchase_log` written only for successes (history stays truthful). List marked `sent_to_kroger` if ≥1 item pushed; failures returned for retry. |
| `Invalid.UPC` / `Invalid.modality` / `Invalid.parameters` | That item fails and is surfaced for retry / buy-in-person; never logged. |
| Item out of stock | `stockLevel=TEMPORARILY_OUT_OF_STOCK` surfaced at match/review; user may keep, swap, or mark buy-in-person. Non-blocking. |
| `total_qty=None` / incompatible units | `purchase_qty=1`, `purchase_qty_estimated=true`; review UI flags it. Never guesses a wrong number. |
| Kroger rate limit (429) / 5xx | Surface a clear "Kroger unavailable, try later" rather than crash; product/location lookups cached per request. No automatic hammering. |
| Not connected / no store picked | `/list/match` and `/list/send` return a clear `409` guiding the user to connect Kroger / pick a store first. |

Principle: `purchase_log` only ever records what truly hit the cart, and Kroger failures degrade
gracefully instead of corrupting Bushel's own data.

## Frontend (functional, Phase 2/3 style)

New screens under `frontend/src/`:

- **Kroger connect / status** — shows connected state; "Connect Kroger" launches `GET /kroger/login`;
  handles the callback return; "Reconnect" on `reauth_required`.
- **Store picker** — zip input → store list from `/kroger/locations` → select sets the list's store.
- **Match / review** — per item: current product (or search results with price/stock), a confirm
  action, manual-search box, "buy in person" toggle, editable `purchase_qty` with the estimated
  flag; a modality selector (PICKUP/DELIVERY) and a "Send to Kroger cart" action showing per-item
  results afterward.

## Testing strategy

Mirrors Phase 2/3: deterministic core unit-tested, all network mocked in CI, one manual live
smoke test.

- **`matching/purchase.py`** — pure table-driven tests: `(total_qty, total_unit, package_size)` →
  `(purchase_qty, estimated)`. Covers compatible-unit ceil math, `total_qty=None`, incompatible
  units, unparseable `package_size`. No network. Correctness-critical.
- **`kroger/client.py`** — tested against recorded fixtures (saved JSON for token, locations,
  products, a `PUT /v1/cart/add` 200, a 401, and an `Invalid.UPC` response). `httpx` transport
  mocked; asserts correct URLs/verbs/payloads. No network in CI.
- **`kroger/auth.py`** — `get_valid_token()`: valid passthrough, expired→refresh,
  refresh-failure→`reauth_required`. Clock/refresh mocked.
- **`matching/service.py`** — over a seeded DB: confirm upserts `ingredient_product_map` + sets
  item UPC; send does tolerant per-item push (incl. partial-failure case), writes `purchase_log`
  for successes only, marks list `sent_to_kroger`. Kroger client mocked.
- **Frontend** — vitest component tests for connect / store-picker / match-review screens against
  a mocked API.

### Manual live smoke test (checklist; run by the user, not CI)

1. Set real `kroger_client_id` / `kroger_client_secret` in `.env`; redirect URI registered.
2. Connect Kroger via the UI → confirm `kroger_auth` row written, `/kroger/status` = connected.
3. Pick a store by zip → confirm `store_location_id` set on the draft.
4. Match one item → search returns products with price/stock → confirm a product.
5. Send → confirm the item appears in the real Kroger cart (Kroger app/site), `purchase_log` row
   written, list marked `sent_to_kroger`.

## Local run note

The test suite spins up a standalone `bushel-pg` Postgres on host port 5432, which conflicts with
the Docker Compose `db` service (also 5432). `docker stop bushel-pg` before `docker compose up`.

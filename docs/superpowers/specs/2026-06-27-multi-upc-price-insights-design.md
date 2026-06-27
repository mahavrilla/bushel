# Multi-UPC ingredients with price insights — design

**Date:** 2026-06-27
**Status:** Approved design, ready for implementation plan

## Problem

An ingredient sometimes has more than one acceptable Kroger product. Example: Califia
almond creamer comes in an organic and a regular version — either is fine, and the user
wants whichever is cheaper or on sale this trip. Today Bushel remembers exactly one
product per ingredient (`ingredient_product_map` is used 1:1), so there is no way to hold
a set of interchangeable UPCs or to compare their current prices.

## Goal

Let an ingredient map to **multiple acceptable UPCs**. When building a trip, default to the
last-purchased one but surface price insights — which alternative is cheaper, which is on
sale, which is out of stock — and let the user switch with one tap. Bushel never
auto-switches; it only surfaces.

## Decisions (from brainstorming)

1. **Surface, never auto-switch.** Default stays last-purchased. Bushel shows insight
   badges and the user taps to switch. (Decision A.)
2. **Manual, additive candidate set.** The set of acceptable UPCs grows only when the user
   explicitly blesses a product as an alternative. Bushel never guesses interchangeability,
   so it only ever compares things the user has said are equivalent. (Decision A.)
3. **Cached prices with a 12h freshness window.** Only multi-UPC items trigger lookups;
   single-product ingredients cost zero API calls. (Decision B, 12h.)
4. **"Cheaper" shows both sticker and unit price.** Lead with sticker price (what you pay),
   show `$/unit` as a secondary line when the package size parses, fall back to sticker-only
   when it doesn't. (Decision C.)
5. **Inline badge + expand in the Cart tab**, with the existing picker kept for adding new
   alternatives. (Decision A.)

## Constraints from the Kroger Products API

- Price (`price.regular`, `price.promo`), `nationalPrice`, `stockLevel`, and fulfillment
  flags are **only returned when `filter.locationId` is included** in the request. No home
  store set → no insights.
- **10,000 calls/day** rate limit across the whole `/products` endpoint.
- Product search is fuzzy (result order varies); we resolve known UPCs via
  `GET /v1/products/{id}` rather than re-searching.

## Pricing semantics

- **Effective price** = `promo` if a promo is present and below `regular`, else `regular`.
- **On sale** = a promo is present and below `regular`.
- **Cheaper** comparison ranks acceptable UPCs by effective price.
- **Unit price** = effective price ÷ parsed package size. Kroger `size` is free-text
  ("25 fl oz", "32 oz", "6 ct"); when it cannot be parsed, omit the `$/unit` line rather
  than fabricate one. Unit prices are only compared when both sizes parse to the same
  dimension.

## Default resolution order

For a multi-UPC item, the current pick resolves as:

1. Most recently purchased acceptable UPC (from `purchase_log`), else
2. the `is_default=True` row, else
3. the only / first row.

Switching the pick on a trip writes the chosen UPC to the list item only; it does **not**
rewrite purchase history. The last-purchased default updates naturally when a trip is sent
and the purchase log is appended.

## Data model

The `ingredient_product_map` table already supports multiple rows per ingredient and
already has `is_default` and `last_confirmed_at`. The change is to start writing more than
one row per ingredient and to compute the default per the order above.

New table **`price_cache`**:

| column | type | notes |
| --- | --- | --- |
| `id` | int PK | |
| `kroger_upc` | str | |
| `location_id` | str | home store the price was fetched for |
| `regular_cents` | int nullable | |
| `promo_cents` | int nullable | |
| `size_text` | str nullable | raw Kroger size string |
| `stock_level` | str nullable | HIGH / LOW / TEMPORARILY_OUT_OF_STOCK |
| `fetched_at` | datetime | freshness basis |

Unique on `(kroger_upc, location_id)`. Freshness window: 12h.

## Price fetch & cache flow

When the match/cart state is built:

1. For each acceptable UPC of a **multi-UPC** item, read `price_cache` for `(upc,
   home_location_id)`.
2. If the row is missing or `fetched_at` is older than 12h, fetch via
   `GET /v1/products/{id}` with `filter.locationId = home store` and upsert the cache row.
3. Single-UPC items and the case of no home store skip all of this.

Because the draft list recomputes on every recipe/staple change, the cache is what keeps
that from re-hitting the API each time.

### Graceful degradation (house rule: never fabricate, never block)

- No home `locationId` set → no insights; show the pick as today.
- Price missing for a UPC → show "price unavailable"; never block the row.
- Size unparseable → sticker price only, no `$/unit` line.

## Backend API

Lives alongside the existing `matching/` module (`service.py`, `router.py`, `schemas.py`)
and `kroger/client.py`.

- **Match/cart state (GET)** gains, per item:
  - `alternatives[]`: each with `upc`, `description`, `size`, `regular`, `promo`,
    `effective`, `unit_price` (nullable), `on_sale`, `stock_level`, `is_current`,
    `price_as_of`.
  - item-level `insight` summary so the row badge needs no client-side math (e.g.
    cheapest-alt delta in cents, on-sale flag, default-out-of-stock flag).
- **Add alternative (POST):** bless a searched product as an acceptable UPC for the
  ingredient (reuses the product picker).
- **Switch pick (POST):** set the chosen UPC as the current pick for this list item
  (writes `grocery_list_items.kroger_upc`); does not touch purchase history.
- **Remove alternative (DELETE):** drop a UPC from the acceptable set.

## Frontend (CartTab + ProductPickerModal)

- **Single-UPC rows are unchanged.**
- **Multi-UPC row, collapsed:** current pick + a compact insight badge row —
  `↓ $X cheaper alt`, `🏷 on sale`, and/or `⚠ default out of stock` — with a "tap to
  compare" caret.
- **Multi-UPC row, expanded:** each acceptable UPC as a line with a stock dot
  (green/amber/red), description and size, sticker price (promo struck-through when on
  sale), `$/unit` when parseable, a "current" marker on the active pick, and a **Use this**
  button on the others. Footer has a "+ find similar…" link (opens the existing picker to
  add a new alternative) and a subtle "prices ~Nh ago".

UI mockup approved during brainstorming
(`.superpowers/brainstorm/.../content/cart-row.html`).

## Edge cases

- Out-of-stock default is surfaced via badge, never auto-switched.
- Cache respected on list recompute so rebuild-on-every-change stays within budget.
- Fuzzy search only matters when *adding* an alternative (via the picker); known UPCs are
  resolved by id.

## Testing

- Default-resolution order: last-purchased → `is_default` → first.
- Effective-price and on-sale logic (promo present/absent, promo ≥ regular).
- Cache hit / miss / 12h expiry.
- Size-parse success vs failure → `$/unit` present vs omitted; unit comparison only within
  the same dimension.
- Multi-UPC vs single-UPC rendering.
- Switch-pick writes the item UPC without touching purchase history.
- No-home-store and price-unavailable degradation paths.

## Out of scope

- Auto-switching or rule-driven selection ("always cheapest", "prefer organic unless
  >$2 more"). Possible later (Decision C from question 1 / B from question 2).
- Auto-suggesting interchangeable products. The candidate set stays manual for now.

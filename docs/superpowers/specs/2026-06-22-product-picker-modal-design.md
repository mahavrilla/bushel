# Kroger product-picker modal — design

Date: 2026-06-22

## Goal

Make it easy to find and select the *right* Kroger product when matching a grocery-list
item. Today, searching (e.g.) "peanut butter" returns only 10 fuzzy results in a cramped
inline list with no images, no way to refine the search term, and no pagination — so the
desired product often isn't shown or can't be told apart from similar ones.

Replace the inline product picker on the **Review & send** screen with a modal that lets
the user refine the search term, page through more results, filter/sort, and visually
identify products by image and brand.

## Scope

- Applies to the **Review & send** (`MatchAndSend`) screen only. This covers staples too,
  because staple products are chosen there (staples fold into the grocery list as items).
- Not in scope: pre-assigning default products to staples on the Staples screen; changing
  how matches are remembered/applied; any change to the send-to-cart flow.

## Background / current state

- **Kroger client** (`backend/app/kroger/client.py`) `search_products(token, term,
  location_id, limit=10)` calls `GET /v1/products` with `filter.term`, `filter.locationId`,
  `filter.limit`. It parses `upc`, `description`, `items[0].size`,
  `items[0].price.regular`, `items[0].inventory.stockLevel` into a `Product`. No `brand`,
  no image, no pagination.
- **Kroger Products API** (per Kroger docs): term search is fuzzy and result order can
  change between identical requests. Pagination uses `filter.start` (number of results to
  skip) and `filter.limit` (page size). A product record also carries a top-level `brand`
  and an `images` array (each with `perspective`, `featured`, and `sizes[].{size,url}`).
- **Matching service** (`backend/app/matching/service.py`) `search_item_products(db,
  client, item_id, query)` resolves the home store, defaults the term to the item's
  ingredient `canonical_name` when `query` is None, and maps `Product` → `ProductChoice`.
- **Endpoint** `GET /list/items/{item_id}/products?q=` (`matching/router.py`).
- **Frontend** `MatchAndSend.tsx` renders, per item, a "Find product"/"Change" button that
  fetches results and lists them inline (`description`, size, price, stock pill, "Choose").
  Choosing calls `confirmProduct` (`POST /list/items/{item_id}/product` with `kroger_upc`,
  `kroger_description`, `package_size`). `ProductChoice` (frontend type + backend schema)
  has `upc`, `description`, `size`, `price`, `stock_level`.
- **UI kit** (`frontend/src/components/ui/`) has Button, Card, EmptyState, ErrorBanner,
  Input, PageHeader, Pill, Spinner — **no modal/dialog component**.

## Approach

Server returns **pages** of products via `filter.start`. The modal accumulates results
across "Load more" clicks and **de-duplicates by UPC** — required because the fuzzy term
search reorders results between requests, so paging would otherwise surface duplicates.
"In stock only" and sort are applied **client-side** over the accumulated list (server-side
filtering/sorting would fight the unstable ordering and is overkill for a personal app).

## Backend changes

### Richer product data
- Add `brand: str | None` and `image_url: str | None` to `Product`
  (`backend/app/kroger/schemas.py`) and to `ProductChoice`
  (`backend/app/matching/schemas.py`).
- In `search_products`, parse (defensively, like the existing `upc` guard):
  - `brand` from the top-level `row.get("brand")`.
  - `image_url`: from `row.get("images")`, prefer the image with `featured == True`, else
    `perspective == "front"`, else the first image; within that image's `sizes`, prefer
    `size == "medium"`, else the first entry with a `url`. `None` if none found.
- `search_item_products` maps the two new fields through to `ProductChoice`.

### Pagination
- `search_products(token, term, location_id, limit=24, start=0)` adds `filter.start` to the
  request params (omit or send 0 when start is 0).
- `search_item_products(db, client, item_id, query, start=0, limit=24)` forwards `start`/
  `limit` to the client.
- `GET /list/items/{item_id}/products` adds query params `start: int = 0` and
  `limit: int = 24` (alongside existing `q`). Existing error handling (404 item,
  409 no store, 502 auth, 503 unavailable) is unchanged.

## Frontend changes

### New `Modal` UI component (`frontend/src/components/ui/Modal.tsx`)
- Props: `{ title: string; onClose: () => void; children }`.
- Renders a fixed full-screen overlay with a centered `Card`-style panel; `role="dialog"`,
  `aria-label={title}`. Closes on backdrop click and on Escape key. A header row shows the
  title and a close (✕) button with `aria-label="Close"`.

### New `ProductPickerModal` (`frontend/src/recipes/ProductPickerModal.tsx`)
- Props: `{ itemId: number; ingredientName: string | null; onChoose: (p: ProductChoice) =>
  void | Promise<void>; onClose: () => void }`.
- State: `query` (initialized to `ingredientName ?? ""`), `results: ProductChoice[]`,
  `start`, `inStockOnly: boolean`, `sort: "relevance" | "price"`, `loading`, `error`.
- On open and on "Search": fetch `searchItemProducts(itemId, query, 0, 24)`, replace
  `results`, set `start = 24`.
- "Load more": fetch `searchItemProducts(itemId, query, start, 24)`, append results
  de-duped by `upc`, advance `start` by 24. Hidden/disabled when the last page returned
  fewer than 24 items.
- Derived view: filter out `stock_level === "TEMPORARILY_OUT_OF_STOCK"` when `inStockOnly`;
  sort by `price` ascending (nulls last) when `sort === "price"`, else keep accumulated
  order ("relevance").
- Each result row shows the image (`image_url`, with a graceful fallback when null),
  `brand`, `description`, `size`, `price`, a stock `Pill` for out-of-stock, and a "Choose"
  button calling `onChoose(product)`.
- Errors surface via `ErrorBanner` (reuse MatchAndSend's existing 409/other messaging
  pattern: expired session → reconnect message; otherwise generic).

### `MatchAndSend.tsx`
- Replace the inline `find()` + results list with: a "Find product"/"Change" button per
  item that opens `ProductPickerModal` for that item (track the open item in state).
- `onChoose` calls the existing `confirmProduct(itemId, { kroger_upc, kroger_description,
  package_size })`, updates the match, and closes the modal.

### api client + types
- `searchItemProducts(itemId, q, start = 0, limit = 24)` → `GET
  /list/items/{itemId}/products?q=&start=&limit=`.
- `ProductChoice` (frontend type) gains `brand: string | null` and `image_url: string |
  null`.

## Testing (TDD)

- **Backend:**
  - `tests/test_kroger_client_catalog.py` — `search_products` parses `brand` and
    `image_url` (featured/front, medium-size preference, fallbacks, null when absent) and
    includes `filter.start` in the request params when `start > 0`.
  - `tests/test_matching_*` — `search_item_products` forwards `start`/`limit` and maps the
    new fields; endpoint accepts `start`/`limit` query params.
- **Frontend:**
  - `Modal.test.tsx` — renders title/children, closes on backdrop + Escape + ✕.
  - `ProductPickerModal.test.tsx` — initial search uses the ingredient name; editing the
    term + Search resets results; "Load more" appends and de-dupes by UPC; "In stock only"
    hides out-of-stock; price sort orders ascending; "Choose" calls `onChoose` with the
    product.
  - `MatchAndSend.test.tsx` — clicking "Find product" opens the modal; choosing confirms
    via `confirmProduct` and closes.
  - `api.test.ts` — `searchItemProducts` includes `start`/`limit` in the URL.

## Out of scope / non-goals

- Sort options beyond Relevance and Price (low→high).
- Server-side filtering or sorting.
- Per-staple default product assignment.
- Caching/rate-limit handling beyond what exists (the 10k/day Kroger limit is ample for
  personal use; "Load more" is user-initiated).

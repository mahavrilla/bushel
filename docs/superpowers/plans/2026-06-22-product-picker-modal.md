# Kroger product-picker modal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cramped inline Kroger product picker on the Review & send screen with a modal that lets the user refine the search term, page through more results, filter/sort, and identify products by image + brand.

**Architecture:** Backend enriches product data (brand + image URL) and adds `filter.start` pagination to the Kroger product search. Frontend adds a reusable `Modal` UI component and a `ProductPickerModal` that accumulates paged results (de-duped by UPC, since Kroger's term search is fuzzy), filters/sorts client-side, and is opened per-item from `MatchAndSend`.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic + httpx (backend, `uv` + pytest), React + TypeScript + Vite + Tailwind (frontend, vitest + Testing Library).

---

## Conventions

**Backend tests** run against the isolated test Postgres `bushel_test` on port 5544 (NOT the dev DB on 5432 — the suite's `conftest.py` drops all tables on teardown). Always:

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest <args>
```

**Frontend tests:**

```bash
cd frontend && npm test -- <args>
```

---

## File Structure

**Backend:**
- Modify `backend/app/kroger/schemas.py` — add `brand`, `image_url` to `Product`.
- Modify `backend/app/kroger/client.py` — parse brand + image; add `start` param + `filter.start`.
- Modify `backend/app/matching/schemas.py` — add `brand`, `image_url` to `ProductChoice`.
- Modify `backend/app/matching/service.py` — forward `start`/`limit`; map new fields.
- Modify `backend/app/matching/router.py` — accept `start`/`limit` query params.
- Tests: `backend/tests/test_kroger_client_catalog.py`, `backend/tests/test_matching_service.py`, `backend/tests/test_matching_router.py`.

**Frontend:**
- Modify `frontend/src/api.ts` — `searchItemProducts(itemId, q, start, limit)`.
- Modify `frontend/src/recipes/types.ts` — `ProductChoice` gains `brand?`, `image_url?`.
- Create `frontend/src/components/ui/Modal.tsx` (+ `Modal.test.tsx`).
- Create `frontend/src/recipes/ProductPickerModal.tsx` (+ `ProductPickerModal.test.tsx`).
- Modify `frontend/src/recipes/MatchAndSend.tsx` — open modal per item (remove inline picker).
- Tests: `frontend/src/recipes/krogerApi.test.ts`, `frontend/src/recipes/MatchAndSend.test.tsx`.

**Note on optionality:** `brand`/`image_url` are added as **optional** (`?: string | null`) on the frontend `ProductChoice` type and as `str | None = None` on the backend schemas. This keeps existing test fixtures (which build `ProductChoice` literals without these fields) valid, and the modal renders them conditionally.

---

## Task 1: Backend — enrich product data + pagination in the Kroger client

**Files:**
- Modify: `backend/app/kroger/schemas.py`
- Modify: `backend/app/kroger/client.py`
- Test: `backend/tests/test_kroger_client_catalog.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_kroger_client_catalog.py`:

```python
def test_search_products_parses_brand_and_image():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "Jif Creamy", "brand": "Jif",
             "images": [
                 {"perspective": "front", "featured": True, "sizes": [
                     {"size": "small", "url": "small.jpg"},
                     {"size": "medium", "url": "medium.jpg"},
                 ]},
             ],
             "items": [{"size": "40 oz"}]},
        ]})

    prods = _client(handler).search_products("tok", "peanut butter", "L1")
    assert prods[0].brand == "Jif"
    assert prods[0].image_url == "medium.jpg"


def test_search_products_image_falls_back_when_no_medium():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "X",
             "images": [{"perspective": "back", "sizes": [{"size": "large", "url": "large.jpg"}]}],
             "items": []},
        ]})

    prods = _client(handler).search_products("tok", "x", "L1")
    assert prods[0].image_url == "large.jpg"
    assert prods[0].brand is None


def test_search_products_handles_missing_images():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "X", "items": []},
        ]})

    prods = _client(handler).search_products("tok", "x", "L1")
    assert prods[0].image_url is None


def test_search_products_sends_filter_start_when_paging():
    def handler(request):
        assert request.url.params["filter.start"] == "24"
        assert request.url.params["filter.limit"] == "24"
        return httpx.Response(200, json={"data": []})

    _client(handler).search_products("tok", "x", "L1", limit=24, start=24)


def test_search_products_omits_filter_start_on_first_page():
    def handler(request):
        assert "filter.start" not in request.url.params
        return httpx.Response(200, json={"data": []})

    _client(handler).search_products("tok", "x", "L1", limit=24, start=0)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_kroger_client_catalog.py -k "brand or image or filter_start" -v
```
Expected: FAIL (no `brand`/`image_url` fields; `start` param not accepted).

- [ ] **Step 3: Add the schema fields**

In `backend/app/kroger/schemas.py`, extend `Product`:

```python
class Product(BaseModel):
    upc: str
    description: str
    size: str | None = None
    price: float | None = None
    stock_level: str | None = None
    brand: str | None = None
    image_url: str | None = None
```

- [ ] **Step 4: Add image extraction + pagination to the client**

In `backend/app/kroger/client.py`, add this module-level helper (above the `KrogerClient` class or near `search_products`):

```python
def _extract_image_url(images: list | None) -> str | None:
    """Pick a product image URL: prefer the featured image, then the front perspective,
    else the first; within it prefer the medium size, else the first available URL."""
    if not images:
        return None
    chosen = next((i for i in images if i.get("featured")), None)
    if chosen is None:
        chosen = next((i for i in images if i.get("perspective") == "front"), None)
    if chosen is None:
        chosen = images[0]
    sizes = chosen.get("sizes") or []
    medium = next((s for s in sizes if s.get("size") == "medium" and s.get("url")), None)
    if medium:
        return medium["url"]
    return next((s["url"] for s in sizes if s.get("url")), None)
```

Replace the `search_products` method with:

```python
    def search_products(
        self, token: str, term: str, location_id: str, limit: int = 24, start: int = 0
    ) -> list[Product]:
        params = {"filter.term": term, "filter.locationId": location_id, "filter.limit": limit}
        if start:
            params["filter.start"] = start
        resp = self._http.get(
            "/v1/products",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        self._raise_for_status(resp)
        out: list[Product] = []
        for row in resp.json().get("data", []):
            upc = row.get("upc")
            if not upc:  # skip malformed records rather than crash the whole list
                continue
            items = row.get("items") or []
            first = items[0] if items else {}
            price = (first.get("price") or {}).get("regular")
            stock = (first.get("inventory") or {}).get("stockLevel")
            out.append(
                Product(
                    upc=upc,
                    description=row.get("description", ""),
                    size=first.get("size"),
                    price=price,
                    stock_level=stock,
                    brand=row.get("brand"),
                    image_url=_extract_image_url(row.get("images")),
                )
            )
        return out
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_kroger_client_catalog.py -v
```
Expected: PASS (existing 4 + new 5).

- [ ] **Step 6: Commit**

```bash
git add backend/app/kroger/schemas.py backend/app/kroger/client.py backend/tests/test_kroger_client_catalog.py
git commit -m "feat(kroger): parse product brand + image, support filter.start paging"
```

---

## Task 2: Backend — thread brand/image + pagination through matching

**Files:**
- Modify: `backend/app/matching/schemas.py`
- Modify: `backend/app/matching/service.py`
- Modify: `backend/app/matching/router.py`
- Test: `backend/tests/test_matching_service.py`, `backend/tests/test_matching_router.py`

- [ ] **Step 1: Write/adjust the failing tests**

**(a)** In `backend/tests/test_matching_service.py`, the existing test `test_search_item_products_uses_store_and_canonical_name` asserts the old call signature. Update its final assertion from:

```python
    kroger.search_products.assert_called_once_with("ct", "flour", "L1")
```

to:

```python
    kroger.search_products.assert_called_once_with("ct", "flour", "L1", limit=24, start=0)
```

And extend its `Product` return + assertions to cover the new fields — change the `kroger.search_products.return_value` line to:

```python
    kroger.search_products.return_value = [
        Product(upc="0001", description="AP Flour", size="5 lb", price=3.49,
                stock_level="HIGH", brand="Gold Medal", image_url="img.jpg")
    ]
```

and add after `assert choices[0].upc == "0001"`:

```python
    assert choices[0].brand == "Gold Medal"
    assert choices[0].image_url == "img.jpg"
```

**(b)** Add a new test to `test_matching_service.py` for paging passthrough (place after the test above):

```python
def test_search_item_products_forwards_start_and_limit(db_session):
    gl, ing, item = _draft_with_item(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = []
    service.search_item_products(db_session, kroger, item.id, query="jif", start=24, limit=24)
    kroger.search_products.assert_called_once_with("ct", "jif", "L1", limit=24, start=24)
```

**(c)** Add a new test to `backend/tests/test_matching_router.py` (after `test_search_products_endpoint`):

```python
def test_search_products_endpoint_passes_start_and_limit(db_session):
    gl, ing, it = _seed(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = []
    client = _client(db_session, kroger)
    client.get(f"/list/items/{it.id}/products", params={"q": "jif", "start": 24, "limit": 24})
    kroger.search_products.assert_called_once_with("ct", "jif", "L1", limit=24, start=24)
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_matching_service.py tests/test_matching_router.py -k "search" -v
```
Expected: FAIL (signature mismatch / new fields / new params).

- [ ] **Step 3: Add the schema fields**

In `backend/app/matching/schemas.py`, extend `ProductChoice`:

```python
class ProductChoice(BaseModel):
    upc: str
    description: str
    size: str | None = None
    price: float | None = None
    stock_level: str | None = None
    brand: str | None = None
    image_url: str | None = None
```

- [ ] **Step 4: Forward start/limit + map fields in the service**

In `backend/app/matching/service.py`, replace `search_item_products` with:

```python
def search_item_products(
    db: Session, client: KrogerClient, item_id: int, query: str | None,
    start: int = 0, limit: int = 24,
) -> list[ProductChoice]:
    item = _get_item(db, item_id)
    location_id, _name = settings_service.get_home_store(db)
    if location_id is None:
        raise NoStoreSelectedError("pick a store before searching products")

    ingredient = db.get(Ingredient, item.ingredient_id)
    term = query or (ingredient.canonical_name if ingredient else "")
    token = client.fetch_client_token()
    products = client.search_products(token.access_token, term, location_id, limit=limit, start=start)
    return [
        ProductChoice(
            upc=p.upc, description=p.description, size=p.size,
            price=p.price, stock_level=p.stock_level,
            brand=p.brand, image_url=p.image_url,
        )
        for p in products
    ]
```

- [ ] **Step 5: Accept start/limit query params in the router**

In `backend/app/matching/router.py`, update the `search_products` endpoint signature + call. The current signature is `(item_id, q: str | None = Query(default=None), db=..., kroger=...)`. Change it to:

```python
@router.get("/items/{item_id}/products", response_model=list[ProductChoice])
def search_products(
    item_id: int,
    q: str | None = Query(default=None),
    start: int = Query(default=0),
    limit: int = Query(default=24),
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        return service.search_item_products(db, kroger, item_id, query=q, start=start, limit=limit)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.NoStoreSelectedError as exc:
        raise HTTPException(status_code=409, detail={"error": "no_store", "message": str(exc)})
    except KrogerAuthError as exc:
        raise HTTPException(status_code=502, detail=f"Kroger auth failed: {exc}")
    except KrogerError as exc:
        raise HTTPException(status_code=503, detail=f"Kroger unavailable: {exc}")
```

(Only the signature and the `service.search_item_products(...)` call change; the `except` blocks are unchanged — shown in full so the handler is complete.)

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_matching_service.py tests/test_matching_router.py -v
```
Expected: PASS (all matching service + router tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/matching/schemas.py backend/app/matching/service.py backend/app/matching/router.py backend/tests/test_matching_service.py backend/tests/test_matching_router.py
git commit -m "feat(matching): pass brand/image + start/limit through product search"
```

---

## Task 3: Frontend — api client + types

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/recipes/types.ts`
- Test: `frontend/src/recipes/krogerApi.test.ts`

- [ ] **Step 1: Adjust the failing test**

In `frontend/src/recipes/krogerApi.test.ts`, replace the `searchItemProducts` test with:

```typescript
  it("searchItemProducts hits the per-item products endpoint with paging params", async () => {
    const f = mockFetch([{ upc: "0001", description: "Flour" }]);
    const res = await searchItemProducts(5, "flour", 24, 24);
    expect(res[0].upc).toBe("0001");
    const url = f.mock.calls[0][0] as string;
    expect(url).toContain("/list/items/5/products?q=flour");
    expect(url).toContain("start=24");
    expect(url).toContain("limit=24");
  });

  it("searchItemProducts defaults start to 0 and limit to 24", async () => {
    const f = mockFetch([{ upc: "0001", description: "Flour" }]);
    await searchItemProducts(5, "flour");
    const url = f.mock.calls[0][0] as string;
    expect(url).toContain("start=0");
    expect(url).toContain("limit=24");
  });
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npm test -- src/recipes/krogerApi.test.ts
```
Expected: FAIL (current `searchItemProducts` takes only `q`, no start/limit in URL).

- [ ] **Step 3: Update the api client**

In `frontend/src/api.ts`, replace `searchItemProducts` with:

```typescript
export async function searchItemProducts(
  itemId: number,
  q: string,
  start = 0,
  limit = 24,
): Promise<ProductChoice[]> {
  return json<ProductChoice[]>(
    await fetch(
      `${BASE_URL}/list/items/${itemId}/products?q=${encodeURIComponent(q)}&start=${start}&limit=${limit}`,
    ),
  );
}
```

- [ ] **Step 4: Extend the type**

In `frontend/src/recipes/types.ts`, extend `ProductChoice`:

```typescript
export interface ProductChoice {
  upc: string;
  description: string;
  size: string | null;
  price: number | null;
  stock_level: string | null;
  brand?: string | null;
  image_url?: string | null;
}
```

- [ ] **Step 5: Run the test + typecheck**

```bash
cd frontend && npm test -- src/recipes/krogerApi.test.ts && npx tsc -b
```
Expected: PASS, clean typecheck.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.ts frontend/src/recipes/types.ts frontend/src/recipes/krogerApi.test.ts
git commit -m "feat(web): searchItemProducts paging params + product brand/image type"
```

---

## Task 4: Frontend — Modal UI component

**Files:**
- Create: `frontend/src/components/ui/Modal.tsx`
- Test: `frontend/src/components/ui/Modal.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/ui/Modal.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Modal } from "./Modal";

afterEach(() => vi.restoreAllMocks());

describe("Modal", () => {
  it("renders the title and children", () => {
    render(<Modal title="Choose a product" onClose={() => {}}>Hello</Modal>);
    expect(screen.getByRole("dialog", { name: "Choose a product" })).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("closes on the ✕ button", () => {
    const onClose = vi.fn();
    render(<Modal title="T" onClose={onClose}>x</Modal>);
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes on backdrop click but not on content click", () => {
    const onClose = vi.fn();
    render(<Modal title="T" onClose={onClose}>content</Modal>);
    fireEvent.click(screen.getByText("content"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("modal-backdrop"));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<Modal title="T" onClose={onClose}>x</Modal>);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/components/ui/Modal.test.tsx
```
Expected: FAIL (Modal does not exist).

- [ ] **Step 3: Create the component**

Create `frontend/src/components/ui/Modal.tsx`:

```tsx
import { useEffect } from "react";

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      data-testid="modal-backdrop"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label={title}
        className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-surface shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-line px-4 py-3">
          <h3 className="text-lg font-semibold text-heading">{title}</h3>
          <button
            type="button"
            aria-label="Close"
            className="ml-auto text-xl leading-none text-muted hover:text-heading"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        <div className="overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/components/ui/Modal.test.tsx && npx tsc -b
```
Expected: PASS, clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Modal.tsx frontend/src/components/ui/Modal.test.tsx
git commit -m "feat(web): reusable Modal UI component"
```

---

## Task 5: Frontend — ProductPickerModal

**Files:**
- Create: `frontend/src/recipes/ProductPickerModal.tsx`
- Test: `frontend/src/recipes/ProductPickerModal.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/recipes/ProductPickerModal.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ProductPickerModal } from "./ProductPickerModal";
import type { ProductChoice } from "./types";

afterEach(() => vi.restoreAllMocks());

function p(over: Partial<ProductChoice> & { upc: string }): ProductChoice {
  return {
    description: "desc",
    size: null,
    price: null,
    stock_level: null,
    ...over,
  };
}

describe("ProductPickerModal", () => {
  it("searches with the ingredient name on open", async () => {
    const search = vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      p({ upc: "1", description: "Jif Creamy", brand: "Jif" }),
    ]);
    render(<ProductPickerModal itemId={5} ingredientName="peanut butter" onChoose={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(search).toHaveBeenCalledWith(5, "peanut butter", 0, 24));
    expect(await screen.findByText(/Jif Creamy/)).toBeInTheDocument();
  });

  it("re-searches from the start when the term is edited", async () => {
    const search = vi
      .spyOn(api, "searchItemProducts")
      .mockResolvedValueOnce([p({ upc: "1", description: "old" })])
      .mockResolvedValueOnce([p({ upc: "2", description: "new result" })]);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("old");
    const box = screen.getByRole("searchbox", { name: /search products/i });
    await userEvent.clear(box);
    await userEvent.type(box, "jif natural");
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(5, "jif natural", 0, 24));
    expect(await screen.findByText("new result")).toBeInTheDocument();
    expect(screen.queryByText("old")).not.toBeInTheDocument();
  });

  it("loads more and de-dupes by upc", async () => {
    const page1 = Array.from({ length: 24 }, (_, i) => p({ upc: `a${i}`, description: `prod ${i}` }));
    const page2 = [p({ upc: "a0", description: "prod 0" }), p({ upc: "z", description: "fresh item" })];
    const search = vi
      .spyOn(api, "searchItemProducts")
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("prod 0");
    fireEvent.click(await screen.findByRole("button", { name: /load more/i }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(5, "pb", 24, 24));
    expect(await screen.findByText("fresh item")).toBeInTheDocument();
    expect(screen.getAllByText("prod 0")).toHaveLength(1); // a0 not duplicated
  });

  it("hides out-of-stock items when 'In stock only' is checked", async () => {
    vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      p({ upc: "1", description: "in stock", stock_level: "HIGH" }),
      p({ upc: "2", description: "out of stock", stock_level: "TEMPORARILY_OUT_OF_STOCK" }),
    ]);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("out of stock");
    await userEvent.click(screen.getByRole("checkbox", { name: /in stock only/i }));
    expect(screen.queryByText("out of stock")).not.toBeInTheDocument();
    expect(screen.getByText("in stock")).toBeInTheDocument();
  });

  it("sorts by price ascending", async () => {
    vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      p({ upc: "1", description: "pricey", price: 9 }),
      p({ upc: "2", description: "cheap", price: 2 }),
    ]);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("pricey");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /sort/i }), "price");
    const descs = screen.getAllByTestId("product-desc").map((n) => n.textContent);
    expect(descs).toEqual(["cheap", "pricey"]);
  });

  it("calls onChoose with the product", async () => {
    vi.spyOn(api, "searchItemProducts").mockResolvedValue([p({ upc: "1", description: "Jif" })]);
    const onChoose = vi.fn();
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={onChoose} onClose={vi.fn()} />);
    await screen.findByText("Jif");
    await userEvent.click(screen.getByRole("button", { name: /choose/i }));
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ upc: "1", description: "Jif" }));
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/ProductPickerModal.test.tsx
```
Expected: FAIL (component does not exist).

- [ ] **Step 3: Create the component**

Create `frontend/src/recipes/ProductPickerModal.tsx`:

```tsx
import { useEffect, useState } from "react";

import { ApiError, searchItemProducts } from "../api";
import { Button } from "../components/ui/Button";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import type { ProductChoice } from "./types";

const PAGE = 24;

function dedupe(products: ProductChoice[]): ProductChoice[] {
  const seen = new Set<string>();
  const out: ProductChoice[] = [];
  for (const item of products) {
    if (seen.has(item.upc)) continue;
    seen.add(item.upc);
    out.push(item);
  }
  return out;
}

export function ProductPickerModal({
  itemId,
  ingredientName,
  onChoose,
  onClose,
}: {
  itemId: number;
  ingredientName: string | null;
  onChoose: (product: ProductChoice) => void | Promise<void>;
  onClose: () => void;
}) {
  const [query, setQuery] = useState(ingredientName ?? "");
  const [results, setResults] = useState<ProductChoice[]>([]);
  const [start, setStart] = useState(0);
  const [reachedEnd, setReachedEnd] = useState(false);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [sort, setSort] = useState<"relevance" | "price">("relevance");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(reset: boolean) {
    const from = reset ? 0 : start;
    setLoading(true);
    setError(null);
    try {
      const page = await searchItemProducts(itemId, query.trim(), from, PAGE);
      setResults((prev) => (reset ? page : dedupe([...prev, ...page])));
      setStart(from + PAGE);
      setReachedEnd(page.length < PAGE);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? "Your Kroger session expired — reconnect on the Kroger tab, then try again."
          : "Something went wrong searching products. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    run(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    run(true);
  }

  let view = results;
  if (inStockOnly) view = view.filter((x) => x.stock_level !== "TEMPORARILY_OUT_OF_STOCK");
  if (sort === "price") view = [...view].sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));

  return (
    <Modal title="Choose a product" onClose={onClose}>
      <form onSubmit={onSubmit} className="mb-3 flex items-end gap-2">
        <Input
          type="search"
          label="Search products"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full"
        />
        <Button type="submit">Search</Button>
      </form>

      <div className="mb-3 flex items-center gap-4 text-sm">
        <label className="flex items-center gap-2 text-ink">
          <input
            type="checkbox"
            checked={inStockOnly}
            onChange={(e) => setInStockOnly(e.target.checked)}
          />
          In stock only
        </label>
        <label className="ml-auto flex items-center gap-2 text-ink">
          Sort
          <select
            aria-label="Sort"
            className="rounded-xl border border-line bg-surface px-2 py-1"
            value={sort}
            onChange={(e) => setSort(e.target.value as "relevance" | "price")}
          >
            <option value="relevance">Relevance</option>
            <option value="price">Price: low to high</option>
          </select>
        </label>
      </div>

      {error && <ErrorBanner message={error} />}

      <ul className="flex flex-col gap-2">
        {view.map((item) => (
          <li key={item.upc} className="flex items-center gap-3 rounded-xl border border-line p-2">
            {item.image_url && (
              <img
                src={item.image_url}
                alt={item.description}
                className="h-14 w-14 shrink-0 rounded object-contain"
              />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                {item.brand && <span className="text-sm font-semibold text-heading">{item.brand}</span>}
                <span className="text-sm text-ink" data-testid="product-desc">
                  {item.description}
                </span>
                {item.stock_level === "TEMPORARILY_OUT_OF_STOCK" && <Pill tone="danger">Out of stock</Pill>}
              </div>
              <div className="text-sm text-muted">
                {item.size}
                {item.price != null && ` · $${item.price.toFixed(2)}`}
              </div>
            </div>
            <Button variant="secondary" onClick={() => onChoose(item)}>
              Choose
            </Button>
          </li>
        ))}
      </ul>

      {loading && (
        <div className="flex justify-center py-4">
          <Spinner />
        </div>
      )}
      {!loading && !reachedEnd && view.length > 0 && (
        <div className="mt-3 flex justify-center">
          <Button variant="secondary" onClick={() => run(false)}>
            Load more
          </Button>
        </div>
      )}
    </Modal>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/ProductPickerModal.test.tsx && npx tsc -b
```
Expected: PASS (6 tests), clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/ProductPickerModal.tsx frontend/src/recipes/ProductPickerModal.test.tsx
git commit -m "feat(web): ProductPickerModal (editable term, paging, filter/sort, images)"
```

---

## Task 6: Frontend — wire MatchAndSend to the modal

**Files:**
- Modify: `frontend/src/recipes/MatchAndSend.tsx`
- Test: `frontend/src/recipes/MatchAndSend.test.tsx`

- [ ] **Step 1: Adjust the failing test**

In `frontend/src/recipes/MatchAndSend.test.tsx`, replace the existing `"searches products for an item"` test with one that opens the modal:

```typescript
  it("opens the product modal and searches when Find product is clicked", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const search = vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" },
    ]);
    render(<MatchAndSend />);
    fireEvent.click(await screen.findByRole("button", { name: /find product/i }));
    await waitFor(() => expect(search).toHaveBeenCalledWith(1, "flour", 0, 24));
    expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
  });

  it("confirms the chosen product and closes the modal", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" },
    ]);
    const confirm = vi.spyOn(api, "confirmProduct").mockResolvedValue({
      ...baseMatch,
      items: [{ ...baseMatch.items[0], kroger_upc: "0001",
        current: { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" } }],
    });
    render(<MatchAndSend />);
    fireEvent.click(await screen.findByRole("button", { name: /find product/i }));
    fireEvent.click(await screen.findByRole("button", { name: /choose/i }));
    await waitFor(() =>
      expect(confirm).toHaveBeenCalledWith(1, {
        kroger_upc: "0001",
        kroger_description: "AP Flour",
        package_size: "5 lb",
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
```

(The other existing tests — list items, send cart, reconnect-on-409, and "shows the matched product and a Change action" — stay as-is; the matched-product row still renders `current.description` and a Change button.)

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npm test -- src/recipes/MatchAndSend.test.tsx
```
Expected: FAIL (no modal; old inline picker calls `searchItemProducts(1,"flour")`).

- [ ] **Step 3: Rewrite the component**

Replace the entire contents of `frontend/src/recipes/MatchAndSend.tsx` with:

```tsx
import { useEffect, useState } from "react";

import { ApiError, confirmProduct, getMatch, sendCart } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import { ProductPickerModal } from "./ProductPickerModal";
import type { MatchData, MatchItem, ProductChoice, SendResult } from "./types";

export function MatchAndSend() {
  const [match, setMatch] = useState<MatchData | null>(null);
  const [openItem, setOpenItem] = useState<MatchItem | null>(null);
  const [modality, setModality] = useState("PICKUP");
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMatch().then(setMatch).catch(() => setMatch(null));
  }, []);

  function report(err: unknown) {
    if (err instanceof ApiError && err.status === 409) {
      setError("Your Kroger session expired — reconnect on the Kroger tab, then try again.");
    } else {
      setError("Something went wrong talking to Kroger. Please try again.");
    }
  }

  async function pick(product: ProductChoice) {
    if (openItem === null) return;
    setError(null);
    try {
      setMatch(
        await confirmProduct(openItem.item_id, {
          kroger_upc: product.upc,
          kroger_description: product.description,
          package_size: product.size,
        }),
      );
      setOpenItem(null);
    } catch (err) {
      report(err);
    }
  }

  async function send() {
    setError(null);
    try {
      setSendResult(await sendCart(modality));
      setMatch(await getMatch());
    } catch (err) {
      report(err);
    }
  }

  if (!match)
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Review &amp; send</h3>
      {error && <ErrorBanner message={error} />}
      {!match.connected && <p className="text-sm text-muted">Connect your Kroger account first.</p>}
      {!match.store_location_id && <p className="text-sm text-muted">Pick a home store first.</p>}

      <ul className="flex flex-col gap-3">
        {match.items.map((it) => (
          <li key={it.item_id} className="rounded-xl border border-line p-3">
            <div className="flex flex-wrap items-center gap-2">
              <strong className="text-heading">{it.ingredient_name}</strong>
              <span className="text-sm text-muted">
                need {it.total_qty ?? "?"} {it.total_unit ?? ""}; buy {it.purchase_qty}
              </span>
              {it.purchase_qty_estimated && <Pill tone="warning">Check quantity</Pill>}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-ink">
                {it.current
                  ? `Product: ${it.current.description}${it.current.size ? ` (${it.current.size})` : ""}`
                  : "No product chosen yet"}
              </span>
              <Button variant="secondary" className="ml-auto" onClick={() => setOpenItem(it)}>
                {it.current ? "Change" : "Find product"}
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Modality</span>
          <select
            className="rounded-xl border border-line bg-surface px-3 py-2 text-ink"
            value={modality}
            onChange={(e) => setModality(e.target.value)}
          >
            <option value="PICKUP">Pickup</option>
            <option value="DELIVERY">Delivery</option>
          </select>
        </label>
        <Button className="ml-auto" onClick={send}>
          Send to Kroger cart
        </Button>
      </div>

      {sendResult && (
        <div className="rounded-xl bg-cream p-3">
          <p className="text-sm font-medium text-heading">Status: {sendResult.status}</p>
          <ul className="mt-1 flex flex-col gap-1">
            {sendResult.results.map((r) => (
              <li key={r.upc} className="text-sm">
                {r.upc}: {r.ok ? "added" : `failed — ${r.error}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {openItem && (
        <ProductPickerModal
          itemId={openItem.item_id}
          ingredientName={openItem.ingredient_name}
          onChoose={pick}
          onClose={() => setOpenItem(null)}
        />
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/MatchAndSend.test.tsx && npx tsc -b
```
Expected: PASS (all MatchAndSend tests), clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/MatchAndSend.tsx frontend/src/recipes/MatchAndSend.test.tsx
git commit -m "feat(web): open ProductPickerModal from Review & send"
```

---

## Task 7: Full verification

- [ ] **Step 1: Full backend suite**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest -q
```
Expected: all tests pass.

- [ ] **Step 2: Full frontend suite + build**

```bash
cd frontend && npm test && npm run build
```
Expected: all tests pass; build succeeds, no type errors.

- [ ] **Step 3: Manual smoke (optional)**

Launch the app (`/run` skill or `docker compose up`), go to Review & send, click "Find product" on an item:
- The modal opens and shows results with images/brand.
- Edit the term (e.g. "jif natural peanut butter") and Search — results refresh.
- "Load more" appends more results without duplicates.
- Toggle "In stock only" and switch sort to "Price: low to high".
- Click "Choose" — the modal closes and the row shows the chosen product.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** brand+image parsing → Task 1; pagination (`filter.start`) → Tasks 1–3; endpoint params → Task 2; api/types → Task 3; Modal → Task 4; editable term + load-more + dedupe + in-stock + sort + images → Task 5; MatchAndSend wiring → Task 6. All spec sections map to a task.
- **Type consistency:** `searchItemProducts(itemId, q, start, limit)` is identical across api.ts (Task 3), ProductPickerModal (Task 5), and the tests. `ProductChoice` brand/image_url optional across backend schemas (Tasks 1–2) and frontend type (Task 3). `search_products(token, term, location_id, limit, start)` consistent between client (Task 1) and service call + assertions (Task 2).
- **Known fixture caveat:** `ProductChoice` literals in tests omit `brand`/`image_url`; these are optional so they remain valid. The "shows the matched product" MatchAndSend test is unchanged and still passes.
- **Fuzzy-order safety:** the load-more test deliberately includes an overlapping UPC across pages to prove de-dup.

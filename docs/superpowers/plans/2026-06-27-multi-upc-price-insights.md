# Multi-UPC Ingredients with Price Insights — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an ingredient map to multiple acceptable Kroger UPCs, default to the last-purchased one, and surface cheaper / on-sale / out-of-stock insights in the Cart tab so the user can switch with one tap.

**Architecture:** The `ingredient_product_map` table already holds multiple rows per ingredient (it has `is_default`); we activate that. A new `price_cache` table stores per-UPC-per-store prices with a 12h freshness window so only multi-UPC items ever hit the Kroger API and list rebuilds don't re-fetch. Pricing math lives in pure helper functions; the Kroger client gains a by-UPC product-detail call. The Cart tab renders an insight badge per multi-UPC row that expands to an inline comparison.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Alembic, `httpx` (+ `MockTransport` in tests), pytest; React + TypeScript + Vitest + Testing Library.

## Global Constraints

- **Kroger prices require `filter.locationId`.** No home store set → no price insights; degrade, never block.
- **10,000 Kroger calls/day.** Only multi-UPC items trigger lookups; the 12h `price_cache` absorbs the app's rebuild-on-every-change.
- **Effective price** = `promo` if present and below `regular`, else `regular`. **On sale** = promo present and below regular.
- **Default resolution order:** most-recently-purchased acceptable UPC (`purchase_log.purchased_at`) → the `is_default=True` row → the first row.
- **Switching a pick never rewrites purchase history.** It only writes `grocery_list_items.kroger_upc`. The last-purchased default updates when a trip is sent.
- **Never fabricate, never block:** price missing → "price unavailable"; size unparseable → no `$/unit` line; no store → no insights.
- Prices are stored as **integer cents** in the DB and converted to dollar floats only at the API boundary.
- Single-UPC ingredients (0 or 1 acceptable mapping) render exactly as today: `alternatives: []`, `insight: null`.
- Backend tests run with `uv run pytest` from `backend/`. Frontend tests run with `npm test` (`vitest run`) from `frontend/`. Tests build tables via `Base.metadata.create_all`, so a new model is picked up automatically; the Alembic migration is for production only.
- Current Alembic head is `f6a7b8c9d0e1`.

---

## File Structure

**Create:**
- `backend/app/matching/pricing.py` — pure price math (effective, on-sale, unit price). No I/O.
- `backend/app/matching/price_cache.py` — read/refresh `price_cache` rows with a 12h window.
- `backend/migrations/versions/a1b2c3d4e5f6_add_price_cache.py` — the `price_cache` table.
- `backend/tests/test_pricing.py`, `backend/tests/test_price_cache.py`, `backend/tests/test_matching_multi_upc.py` — new tests.

**Modify:**
- `backend/app/kroger/schemas.py` — add `promo` to `Product`.
- `backend/app/kroger/client.py` — capture `promo` in `search_products`; add `get_product_by_id`.
- `backend/app/models.py` — add `PriceCache`.
- `backend/app/matching/schemas.py` — add `Alternative`, `ItemInsight`; extend `MatchItemRead`; add request bodies.
- `backend/app/matching/service.py` — multi-UPC resolution, alternatives/insight assembly, `add_alternative`/`remove_alternative`/`switch_pick`.
- `backend/app/matching/router.py` — new endpoints; thread the Kroger client into state-returning routes.
- `frontend/src/recipes/types.ts` — add `Alternative`, `ItemInsight`; extend `ProductChoice`, `MatchItem`.
- `frontend/src/api.ts` — `addAlternative`, `removeAlternative`, `switchPick`.
- `frontend/src/recipes/CartTab.tsx` — badges + inline comparison + wiring.
- `frontend/src/recipes/ProductPickerModal.tsx` — "add alternative" mode (title/CTA only).

---

## Task 1: Kroger client — capture promo + add by-UPC product detail

**Files:**
- Modify: `backend/app/kroger/schemas.py:21-28` (Product)
- Modify: `backend/app/kroger/client.py:151-183` (search_products) and add `get_product_by_id`
- Test: `backend/tests/test_kroger_client_catalog.py`

**Interfaces:**
- Produces: `Product.promo: float | None`; `KrogerClient.get_product_by_id(token: str, upc: str, location_id: str) -> Product`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_kroger_client_catalog.py`:

```python
def test_search_products_captures_promo():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "Creamer",
             "items": [{"size": "32 fl oz",
                        "price": {"regular": 5.49, "promo": 4.29},
                        "inventory": {"stockLevel": "HIGH"}}]},
        ]})

    prods = _client(handler).search_products("tok", "creamer", "L1")
    assert prods[0].price == 5.49
    assert prods[0].promo == 4.29


def test_get_product_by_id_parses_price_and_stock():
    def handler(request):
        assert request.url.path == "/v1/products/0001"
        assert request.url.params["filter.locationId"] == "L1"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"data": {
            "upc": "0001", "description": "Califia Organic",
            "items": [{"size": "25 fl oz",
                       "price": {"regular": 5.99, "promo": 4.29},
                       "inventory": {"stockLevel": "LOW"}}]}})

    prod = _client(handler).get_product_by_id("tok", "0001", "L1")
    assert prod.upc == "0001"
    assert prod.size == "25 fl oz"
    assert prod.price == 5.99
    assert prod.promo == 4.29
    assert prod.stock_level == "LOW"


def test_get_product_by_id_handles_data_as_object_or_missing_items():
    def handler(request):
        return httpx.Response(200, json={"data": {"upc": "0001", "description": "X", "items": []}})

    prod = _client(handler).get_product_by_id("tok", "0001", "L1")
    assert prod.upc == "0001"
    assert prod.price is None
    assert prod.promo is None
    assert prod.size is None


def test_get_product_by_id_5xx_raises_unavailable():
    def handler(request):
        return httpx.Response(503, json={})

    with pytest.raises(KrogerUnavailableError):
        _client(handler).get_product_by_id("tok", "0001", "L1")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_kroger_client_catalog.py -k "promo or get_product_by_id" -v`
Expected: FAIL (`Product` has no `promo`; `get_product_by_id` does not exist).

- [ ] **Step 3: Add `promo` to the Product schema**

In `backend/app/kroger/schemas.py`, add the field to `Product` (after `price`):

```python
class Product(BaseModel):
    upc: str
    description: str
    size: str | None = None
    price: float | None = None
    promo: float | None = None
    stock_level: str | None = None
    brand: str | None = None
    image_url: str | None = None
```

- [ ] **Step 4: Capture promo in search_products and add get_product_by_id**

In `backend/app/kroger/client.py`, inside `search_products`, where `price` is read, also read promo and pass it through:

```python
            items = row.get("items") or []
            first = items[0] if items else {}
            price_obj = first.get("price") or {}
            price = price_obj.get("regular")
            promo = price_obj.get("promo")
            stock = (first.get("inventory") or {}).get("stockLevel")
            out.append(
                Product(
                    upc=upc,
                    description=row.get("description", ""),
                    size=first.get("size"),
                    price=price,
                    promo=promo,
                    stock_level=stock,
                    brand=row.get("brand"),
                    image_url=_extract_image_url(row.get("images")),
                )
            )
```

Then add this method to `KrogerClient` (below `search_products`):

```python
    def get_product_by_id(self, token: str, upc: str, location_id: str) -> Product:
        """Fetch a single product's detail (price/promo/stock/size) for a known UPC at a
        store. The /products/{id} endpoint accepts a UPC as the id and returns a single
        object under 'data'. Used to price the acceptable alternatives of a multi-UPC item."""
        resp = self._http.get(
            f"/v1/products/{upc}",
            params={"filter.locationId": location_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        self._raise_for_status(resp)
        row = resp.json().get("data") or {}
        if isinstance(row, list):  # tolerate either shape the API may return
            row = row[0] if row else {}
        items = row.get("items") or []
        first = items[0] if items else {}
        price_obj = first.get("price") or {}
        return Product(
            upc=row.get("upc", upc),
            description=row.get("description", ""),
            size=first.get("size"),
            price=price_obj.get("regular"),
            promo=price_obj.get("promo"),
            stock_level=(first.get("inventory") or {}).get("stockLevel"),
            brand=row.get("brand"),
            image_url=_extract_image_url(row.get("images")),
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_kroger_client_catalog.py -v`
Expected: PASS (all, including the pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/kroger/schemas.py backend/app/kroger/client.py backend/tests/test_kroger_client_catalog.py
git commit -m "feat(kroger): capture promo price and add get_product_by_id"
```

---

## Task 2: Pricing math (pure functions)

**Files:**
- Create: `backend/app/matching/pricing.py`
- Test: `backend/tests/test_pricing.py`

**Interfaces:**
- Produces:
  - `effective_cents(regular_cents: int | None, promo_cents: int | None) -> int | None`
  - `is_on_sale(regular_cents: int | None, promo_cents: int | None) -> bool`
  - `unit_price(effective_cents: int | None, size_text: str | None) -> tuple[float, str] | None` — returns `(dollars_per_unit, unit_label)`.
  - `to_cents(dollars: float | None) -> int | None`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_pricing.py`:

```python
from app.matching import pricing


def test_to_cents_rounds_and_passes_none():
    assert pricing.to_cents(5.49) == 549
    assert pricing.to_cents(4.295) == 430
    assert pricing.to_cents(None) is None


def test_effective_prefers_promo_when_lower():
    assert pricing.effective_cents(549, 429) == 429


def test_effective_ignores_promo_when_not_lower():
    assert pricing.effective_cents(549, 549) == 549
    assert pricing.effective_cents(549, 600) == 549


def test_effective_uses_regular_when_no_promo():
    assert pricing.effective_cents(549, None) == 549


def test_effective_none_when_no_regular_and_no_promo():
    assert pricing.effective_cents(None, None) is None
    assert pricing.effective_cents(None, 429) == 429


def test_on_sale_true_only_when_promo_below_regular():
    assert pricing.is_on_sale(549, 429) is True
    assert pricing.is_on_sale(549, 549) is False
    assert pricing.is_on_sale(549, None) is False
    assert pricing.is_on_sale(None, 429) is False


def test_unit_price_divides_by_parsed_size():
    dollars, unit = pricing.unit_price(549, "32 fl oz")
    assert round(dollars, 4) == 0.1716
    assert unit == "fl oz"


def test_unit_price_none_when_size_unparseable_or_no_price():
    assert pricing.unit_price(549, "family size") is None
    assert pricing.unit_price(None, "32 fl oz") is None
    assert pricing.unit_price(549, None) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_pricing.py -v`
Expected: FAIL (`app.matching.pricing` does not exist).

- [ ] **Step 3: Write the implementation**

Create `backend/app/matching/pricing.py`:

```python
"""Pure price math for multi-UPC comparison. No DB, no network. Prices are integer cents
except unit_price, which returns dollars-per-unit for display."""

from __future__ import annotations

from app.matching.purchase import parse_package_size


def to_cents(dollars: float | None) -> int | None:
    if dollars is None:
        return None
    return round(dollars * 100)


def effective_cents(regular_cents: int | None, promo_cents: int | None) -> int | None:
    """Promo wins only when present and strictly below regular (or regular is unknown)."""
    if promo_cents is not None and (regular_cents is None or promo_cents < regular_cents):
        return promo_cents
    return regular_cents


def is_on_sale(regular_cents: int | None, promo_cents: int | None) -> bool:
    return (
        regular_cents is not None
        and promo_cents is not None
        and promo_cents < regular_cents
    )


def unit_price(effective_cents: int | None, size_text: str | None) -> tuple[float, str] | None:
    """Dollars per unit, e.g. (0.17, 'fl oz'). None when there is no price or the package
    size cannot be parsed — never fabricate a unit price."""
    if effective_cents is None:
        return None
    parsed = parse_package_size(size_text)
    if parsed is None:
        return None
    qty, unit = parsed
    if qty <= 0:
        return None
    return (effective_cents / 100.0) / qty, unit
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_pricing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/matching/pricing.py backend/tests/test_pricing.py
git commit -m "feat(matching): pure price math (effective, on-sale, unit price)"
```

---

## Task 3: `price_cache` model + migration

**Files:**
- Modify: `backend/app/models.py` (add `PriceCache` at end of file)
- Create: `backend/migrations/versions/a1b2c3d4e5f6_add_price_cache.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `PriceCache` ORM model — columns `id, kroger_upc, location_id, regular_cents, promo_cents, size_text, stock_level, fetched_at`; unique `(kroger_upc, location_id)`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
def test_price_cache_round_trips(db_session):
    from app.models import PriceCache

    row = PriceCache(
        kroger_upc="0001", location_id="L1",
        regular_cents=549, promo_cents=429,
        size_text="32 fl oz", stock_level="HIGH",
    )
    db_session.add(row)
    db_session.flush()
    got = db_session.query(PriceCache).filter_by(kroger_upc="0001", location_id="L1").one()
    assert got.regular_cents == 549
    assert got.promo_cents == 429
    assert got.fetched_at is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/test_models.py::test_price_cache_round_trips -v`
Expected: FAIL (`cannot import name 'PriceCache'`).

- [ ] **Step 3: Add the model**

Append to `backend/app/models.py`:

```python
class PriceCache(Base):
    __tablename__ = "price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kroger_upc: Mapped[str] = mapped_column(String(50))
    location_id: Mapped[str] = mapped_column(String(50))
    regular_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    promo_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stock_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("kroger_upc", "location_id", name="uq_price_cache_upc_loc"),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/test_models.py::test_price_cache_round_trips -v`
Expected: PASS (the test fixture creates the table via `Base.metadata.create_all`).

- [ ] **Step 5: Write the Alembic migration**

Create `backend/migrations/versions/a1b2c3d4e5f6_add_price_cache.py`:

```python
"""add price_cache

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kroger_upc', sa.String(length=50), nullable=False),
        sa.Column('location_id', sa.String(length=50), nullable=False),
        sa.Column('regular_cents', sa.Integer(), nullable=True),
        sa.Column('promo_cents', sa.Integer(), nullable=True),
        sa.Column('size_text', sa.String(length=100), nullable=True),
        sa.Column('stock_level', sa.String(length=40), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kroger_upc', 'location_id', name='uq_price_cache_upc_loc'),
    )


def downgrade() -> None:
    op.drop_table('price_cache')
```

- [ ] **Step 6: Verify the migration applies cleanly**

Run: `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: no errors; `price_cache` created, dropped, recreated. (Requires the dev Postgres from `docker-compose` to be up.)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/migrations/versions/a1b2c3d4e5f6_add_price_cache.py backend/tests/test_models.py
git commit -m "feat(db): add price_cache table"
```

---

## Task 4: Price cache service (12h window, fetch-on-miss)

**Files:**
- Create: `backend/app/matching/price_cache.py`
- Test: `backend/tests/test_price_cache.py`

**Interfaces:**
- Consumes: `KrogerClient.get_product_by_id` (Task 1), `PriceCache` (Task 3), `pricing.to_cents` (Task 2).
- Produces:
  - `PriceInfo` dataclass: `upc, regular_cents, promo_cents, size_text, stock_level, fetched_at`.
  - `FRESH_WINDOW: timedelta` (12 hours).
  - `get_prices(db, client, upcs: list[str], location_id: str, *, now: datetime) -> dict[str, PriceInfo]` — cache-first; fetches missing/stale UPCs via the client and upserts; on a Kroger error for a UPC, skips it (absent from the dict). `now` is injected for deterministic tests.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_price_cache.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.kroger.schemas import Product, TokenResp
from app.matching import price_cache
from app.models import PriceCache

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)


def _client(products: dict[str, Product]) -> MagicMock:
    c = MagicMock()
    c.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    c.get_product_by_id.side_effect = lambda tok, upc, loc: products[upc]
    return c


def test_fresh_cache_row_is_used_without_fetching(db_session):
    db_session.add(PriceCache(kroger_upc="0001", location_id="L1", regular_cents=549,
                              promo_cents=None, size_text="32 fl oz", stock_level="HIGH",
                              fetched_at=NOW - timedelta(hours=11)))
    db_session.flush()
    client = _client({})
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert out["0001"].regular_cents == 549
    client.get_product_by_id.assert_not_called()


def test_stale_row_is_refetched_and_upserted(db_session):
    db_session.add(PriceCache(kroger_upc="0001", location_id="L1", regular_cents=999,
                              promo_cents=None, size_text="32 fl oz", stock_level="HIGH",
                              fetched_at=NOW - timedelta(hours=13)))
    db_session.flush()
    client = _client({"0001": Product(upc="0001", description="C", size="32 fl oz",
                                      price=5.49, promo=4.29, stock_level="LOW")})
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert out["0001"].regular_cents == 549
    assert out["0001"].promo_cents == 429
    assert out["0001"].stock_level == "LOW"
    row = db_session.query(PriceCache).filter_by(kroger_upc="0001", location_id="L1").one()
    assert row.regular_cents == 549
    assert row.fetched_at == NOW


def test_missing_upc_is_fetched(db_session):
    client = _client({"0001": Product(upc="0001", description="C", size="25 fl oz",
                                      price=5.99, promo=None, stock_level="HIGH")})
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert out["0001"].regular_cents == 599
    assert db_session.query(PriceCache).filter_by(kroger_upc="0001").count() == 1


def test_kroger_error_for_a_upc_is_skipped(db_session):
    from app.kroger.client import KrogerUnavailableError

    client = MagicMock()
    client.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    client.get_product_by_id.side_effect = KrogerUnavailableError("boom")
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert "0001" not in out


def test_no_client_returns_only_cached(db_session):
    db_session.add(PriceCache(kroger_upc="0001", location_id="L1", regular_cents=549,
                              promo_cents=None, size_text=None, stock_level=None,
                              fetched_at=NOW))
    db_session.flush()
    out = price_cache.get_prices(db_session, None, ["0001", "0002"], "L1", now=NOW)
    assert "0001" in out and "0002" not in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_price_cache.py -v`
Expected: FAIL (`app.matching.price_cache` does not exist).

- [ ] **Step 3: Write the implementation**

Create `backend/app/matching/price_cache.py`:

```python
"""Read and refresh price_cache rows. The only thing that calls KrogerClient.get_product_by_id.
A 12h freshness window keeps the app's rebuild-on-every-change from re-hitting the API and
keeps us well under the 10k/day budget. now is injected so tests are deterministic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kroger.client import KrogerClient, KrogerError
from app.matching.pricing import to_cents
from app.models import PriceCache

FRESH_WINDOW = timedelta(hours=12)


@dataclass
class PriceInfo:
    upc: str
    regular_cents: int | None
    promo_cents: int | None
    size_text: str | None
    stock_level: str | None
    fetched_at: datetime


def _info(row: PriceCache) -> PriceInfo:
    return PriceInfo(
        upc=row.kroger_upc,
        regular_cents=row.regular_cents,
        promo_cents=row.promo_cents,
        size_text=row.size_text,
        stock_level=row.stock_level,
        fetched_at=row.fetched_at,
    )


def get_prices(
    db: Session,
    client: KrogerClient | None,
    upcs: list[str],
    location_id: str,
    *,
    now: datetime,
) -> dict[str, PriceInfo]:
    if not upcs:
        return {}
    rows = db.execute(
        select(PriceCache).where(
            PriceCache.location_id == location_id,
            PriceCache.kroger_upc.in_(upcs),
        )
    ).scalars().all()
    by_upc = {r.kroger_upc: r for r in rows}

    out: dict[str, PriceInfo] = {}
    stale: list[str] = []
    for upc in upcs:
        row = by_upc.get(upc)
        if row is not None and (now - row.fetched_at) < FRESH_WINDOW:
            out[upc] = _info(row)
        else:
            stale.append(upc)

    if stale and client is not None:
        token = client.fetch_client_token()
        for upc in stale:
            try:
                prod = client.get_product_by_id(token.access_token, upc, location_id)
            except KrogerError:
                continue  # leave this UPC absent; caller shows "price unavailable"
            row = by_upc.get(upc) or PriceCache(kroger_upc=upc, location_id=location_id)
            row.regular_cents = to_cents(prod.price)
            row.promo_cents = to_cents(prod.promo)
            row.size_text = prod.size
            row.stock_level = prod.stock_level
            row.fetched_at = now
            db.add(row)
            out[upc] = _info(row)
        db.flush()

    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_price_cache.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/matching/price_cache.py backend/tests/test_price_cache.py
git commit -m "feat(matching): price_cache service with 12h freshness window"
```

---

## Task 5: Multi-UPC default resolution in matching service

**Files:**
- Modify: `backend/app/matching/service.py` (add helpers; update `_current_choice` and `apply_remembered_products`)
- Test: `backend/tests/test_matching_multi_upc.py` (create)

**Interfaces:**
- Consumes: `IngredientProductMap`, `PurchaseLog`.
- Produces (module-level in `service.py`):
  - `_acceptable_maps(db, ingredient_id) -> list[IngredientProductMap]` — ordered by `id`.
  - `_resolve_default_upc(db, ingredient_id) -> str | None` — last-purchased → is_default → first.
  - `apply_remembered_products` now fills an unresolved item's `kroger_upc` with `_resolve_default_upc` and recomputes qty from that row's `package_size`.
  - `_current_choice` now matches the mapping row whose `kroger_upc == item.kroger_upc`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_matching_multi_upc.py`:

```python
from datetime import datetime, timedelta, timezone

from app.matching import service
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    IngredientProductMap,
    PurchaseLog,
)
from app.settings import service as settings_service


def _draft_with_item(db, total_qty=1.0, total_unit="bottle", store="L1"):
    ing = Ingredient(canonical_name="creamer", aliases=[], category="dairy",
                     default_purchase_unit="bottle")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id=store)
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id,
                           total_qty=total_qty, total_unit=total_unit, pantry_status="needed")
    db.add(item)
    db.flush()
    settings_service.set_home_store(db, store, None) if store else None
    return gl, ing, item


def _two_alts(db, ing):
    db.add_all([
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="REG",
                             kroger_description="Regular", package_size="32 fl oz", is_default=True),
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="ORG",
                             kroger_description="Organic", package_size="25 fl oz", is_default=False),
    ])
    db.flush()


def test_resolve_default_prefers_last_purchased(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    now = datetime.now(timezone.utc)
    db_session.add_all([
        PurchaseLog(ingredient_id=ing.id, kroger_upc="REG", purchased_at=now - timedelta(days=5)),
        PurchaseLog(ingredient_id=ing.id, kroger_upc="ORG", purchased_at=now - timedelta(days=1)),
    ])
    db_session.flush()
    assert service._resolve_default_upc(db_session, ing.id) == "ORG"


def test_resolve_default_falls_back_to_is_default(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    assert service._resolve_default_upc(db_session, ing.id) == "REG"


def test_resolve_default_falls_back_to_first_when_no_default(db_session):
    gl, ing, item = _draft_with_item(db_session)
    db_session.add_all([
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="A", package_size="1 ct", is_default=False),
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="B", package_size="1 ct", is_default=False),
    ])
    db_session.flush()
    assert service._resolve_default_upc(db_session, ing.id) == "A"


def test_resolve_default_ignores_purchase_of_non_acceptable_upc(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    db_session.add(PurchaseLog(ingredient_id=ing.id, kroger_upc="GONE",
                               purchased_at=datetime.now(timezone.utc)))
    db_session.flush()
    assert service._resolve_default_upc(db_session, ing.id) == "REG"  # is_default, not GONE


def test_apply_remembered_uses_resolved_default(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    db_session.add(PurchaseLog(ingredient_id=ing.id, kroger_upc="ORG",
                               purchased_at=datetime.now(timezone.utc)))
    db_session.flush()
    service.apply_remembered_products(db_session)
    db_session.refresh(item)
    assert item.kroger_upc == "ORG"


def test_apply_remembered_keeps_existing_pick(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "ORG"  # user already switched
    db_session.flush()
    service.apply_remembered_products(db_session)
    db_session.refresh(item)
    assert item.kroger_upc == "ORG"


def test_current_choice_matches_item_upc_not_first_row(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "ORG"
    db_session.flush()
    current = service.get_match_state(db_session).items[0].current
    assert current.upc == "ORG"
    assert current.description == "Organic"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_matching_multi_upc.py -v`
Expected: FAIL (`service._resolve_default_upc` does not exist; `_current_choice` returns the first row).

- [ ] **Step 3: Add helpers and update existing functions**

In `backend/app/matching/service.py`, add helpers after `_kept_items`:

```python
def _acceptable_maps(db: Session, ingredient_id: int) -> list[IngredientProductMap]:
    return db.execute(
        select(IngredientProductMap)
        .where(IngredientProductMap.ingredient_id == ingredient_id)
        .order_by(IngredientProductMap.id)
    ).scalars().all()


def _resolve_default_upc(db: Session, ingredient_id: int) -> str | None:
    """Default pick = most recently purchased acceptable UPC, else the is_default row,
    else the first row. Purchases of UPCs no longer in the acceptable set are ignored."""
    rows = _acceptable_maps(db, ingredient_id)
    if not rows:
        return None
    acceptable = {r.kroger_upc for r in rows}
    last = db.execute(
        select(PurchaseLog)
        .where(
            PurchaseLog.ingredient_id == ingredient_id,
            PurchaseLog.kroger_upc.in_(acceptable),
        )
        .order_by(PurchaseLog.purchased_at.desc())
    ).scalars().first()
    if last is not None and last.kroger_upc is not None:
        return last.kroger_upc
    default_row = next((r for r in rows if r.is_default), None)
    if default_row is not None:
        return default_row.kroger_upc
    return rows[0].kroger_upc
```

Replace `_current_choice` so it matches the item's chosen UPC:

```python
def _current_choice(db: Session, item: GroceryListItem) -> ProductChoice | None:
    if item.kroger_upc is None:
        return None
    mapping = db.execute(
        select(IngredientProductMap).where(
            IngredientProductMap.ingredient_id == item.ingredient_id,
            IngredientProductMap.kroger_upc == item.kroger_upc,
        )
    ).scalars().first()
    if mapping is None:
        return ProductChoice(upc=item.kroger_upc, description="")
    return ProductChoice(
        upc=mapping.kroger_upc,
        description=mapping.kroger_description or "",
        size=mapping.package_size,
    )
```

Replace the body of `apply_remembered_products` so it resolves the default and prices qty from the resolved row:

```python
def apply_remembered_products(db: Session) -> None:
    """Fill unresolved kept items with the resolved default UPC (last-purchased → is_default →
    first) and recompute purchase_qty from that product's package size. Idempotent; existing
    picks are left untouched so a user's switch survives list rebuilds."""
    draft = get_or_create_draft(db)
    for item in _kept_items(db, draft.id):
        if item.kroger_upc is not None:
            continue
        upc = _resolve_default_upc(db, item.ingredient_id)
        if upc is None:
            continue
        row = next(
            (r for r in _acceptable_maps(db, item.ingredient_id) if r.kroger_upc == upc),
            None,
        )
        item.kroger_upc = upc
        qty, estimated = compute_purchase_qty(
            item.total_qty, item.total_unit, row.package_size if row else None
        )
        item.purchase_qty = qty
        item.purchase_qty_estimated = estimated
    db.flush()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_matching_multi_upc.py tests/test_matching_apply.py tests/test_matching_service.py -v`
Expected: PASS (new tests plus the existing matching tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/app/matching/service.py backend/tests/test_matching_multi_upc.py
git commit -m "feat(matching): multi-UPC default resolution (last-purchased -> is_default -> first)"
```

---

## Task 6: add / remove / switch service functions

**Files:**
- Modify: `backend/app/matching/service.py` (add three functions + an exception)
- Modify: `backend/app/matching/schemas.py` (request bodies)
- Test: `backend/tests/test_matching_multi_upc.py` (extend)

**Interfaces:**
- Consumes: `_acceptable_maps`, `_resolve_default_upc`, `compute_purchase_qty`, `_get_item`.
- Produces:
  - `AddAlternativeRequest(kroger_upc: str, kroger_description: str | None = None, package_size: str | None = None)`
  - `SwitchPickRequest(kroger_upc: str)`
  - `service.add_alternative(db, item_id, req) -> None` — adds an `IngredientProductMap` row (is_default=False) for the item's ingredient if that UPC isn't already mapped; never changes the current pick.
  - `service.switch_pick(db, item_id, upc) -> None` — sets `item.kroger_upc` to an acceptable UPC and recomputes qty; raises `UpcNotAcceptableError` if the UPC isn't in the set. Does not touch purchase history.
  - `service.remove_alternative(db, item_id, upc) -> None` — deletes the mapping row; if it was the current pick, re-resolves the default (may become `None`).
  - `class UpcNotAcceptableError(Exception)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_matching_multi_upc.py`:

```python
import pytest

from app.matching.schemas import AddAlternativeRequest


def test_add_alternative_appends_row_without_changing_pick(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    service.add_alternative(db_session, item.id,
                            AddAlternativeRequest(kroger_upc="VAN", kroger_description="Vanilla",
                                                  package_size="32 fl oz"))
    db_session.flush()
    upcs = {m.kroger_upc for m in service._acceptable_maps(db_session, ing.id)}
    assert upcs == {"REG", "ORG", "VAN"}
    db_session.refresh(item)
    assert item.kroger_upc == "REG"  # pick unchanged


def test_add_alternative_is_idempotent_on_duplicate_upc(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    service.add_alternative(db_session, item.id, AddAlternativeRequest(kroger_upc="REG"))
    db_session.flush()
    assert len(service._acceptable_maps(db_session, ing.id)) == 2


def test_switch_pick_sets_item_upc_and_recomputes_qty(db_session):
    gl, ing, item = _draft_with_item(db_session, total_qty=2.0, total_unit="bottle")
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    service.switch_pick(db_session, item.id, "ORG")
    db_session.refresh(item)
    assert item.kroger_upc == "ORG"
    assert item.purchase_qty >= 1


def test_switch_pick_rejects_non_acceptable_upc(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    with pytest.raises(service.UpcNotAcceptableError):
        service.switch_pick(db_session, item.id, "NOPE")


def test_switch_pick_does_not_write_purchase_log(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    service.switch_pick(db_session, item.id, "ORG")
    assert db_session.query(PurchaseLog).count() == 0


def test_remove_alternative_repoints_pick_when_removing_current(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)  # REG is_default
    item.kroger_upc = "ORG"
    db_session.flush()
    service.remove_alternative(db_session, item.id, "ORG")
    db_session.refresh(item)
    assert item.kroger_upc == "REG"  # re-resolved to remaining default
    assert {m.kroger_upc for m in service._acceptable_maps(db_session, ing.id)} == {"REG"}


def test_remove_last_alternative_clears_pick(db_session):
    gl, ing, item = _draft_with_item(db_session)
    db_session.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="ONLY",
                                        package_size="1 ct", is_default=True))
    db_session.flush()
    item.kroger_upc = "ONLY"
    db_session.flush()
    service.remove_alternative(db_session, item.id, "ONLY")
    db_session.refresh(item)
    assert item.kroger_upc is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_matching_multi_upc.py -k "add_alternative or switch_pick or remove_alternative" -v`
Expected: FAIL (functions and request schemas do not exist).

- [ ] **Step 3: Add the request schemas**

In `backend/app/matching/schemas.py`, add after `ConfirmRequest`:

```python
class AddAlternativeRequest(BaseModel):
    kroger_upc: str
    kroger_description: str | None = None
    package_size: str | None = None


class SwitchPickRequest(BaseModel):
    kroger_upc: str
```

- [ ] **Step 4: Add the service functions**

In `backend/app/matching/service.py`, add the exception near the top (with the other exception classes):

```python
class UpcNotAcceptableError(Exception):
    """The requested UPC is not in the ingredient's acceptable set."""
```

Update the schema import to include the new request models:

```python
from app.matching.schemas import (
    AddAlternativeRequest,
    ConfirmRequest,
    MatchItemRead,
    MatchRead,
    ProductChoice,
    SendItemResult,
    SendResult,
    SwitchPickRequest,
)
```

Add the three functions (after `confirm_product`):

```python
def add_alternative(db: Session, item_id: int, req: AddAlternativeRequest) -> None:
    """Bless a product as an acceptable alternative for the item's ingredient. No-op if the
    UPC is already mapped. Never changes the current pick."""
    item = _get_item(db, item_id)
    existing = {m.kroger_upc for m in _acceptable_maps(db, item.ingredient_id)}
    if req.kroger_upc in existing:
        return
    db.add(
        IngredientProductMap(
            ingredient_id=item.ingredient_id,
            kroger_upc=req.kroger_upc,
            kroger_description=req.kroger_description,
            package_size=req.package_size,
            is_default=False,
        )
    )
    db.flush()


def switch_pick(db: Session, item_id: int, upc: str) -> None:
    """Set the item's current pick to an acceptable UPC and recompute purchase_qty. Does not
    write purchase history — the last-purchased default only changes when a trip is sent."""
    item = _get_item(db, item_id)
    rows = _acceptable_maps(db, item.ingredient_id)
    row = next((r for r in rows if r.kroger_upc == upc), None)
    if row is None:
        raise UpcNotAcceptableError(f"{upc} is not an acceptable product for this ingredient")
    item.kroger_upc = upc
    qty, estimated = compute_purchase_qty(item.total_qty, item.total_unit, row.package_size)
    item.purchase_qty = qty
    item.purchase_qty_estimated = estimated
    db.flush()


def remove_alternative(db: Session, item_id: int, upc: str) -> None:
    """Drop a UPC from the acceptable set. If it was the current pick, re-resolve the default
    (which may leave the item with no pick)."""
    item = _get_item(db, item_id)
    row = next(
        (r for r in _acceptable_maps(db, item.ingredient_id) if r.kroger_upc == upc), None
    )
    if row is None:
        return
    db.delete(row)
    db.flush()
    if item.kroger_upc == upc:
        new_upc = _resolve_default_upc(db, item.ingredient_id)
        item.kroger_upc = new_upc
        new_row = next(
            (r for r in _acceptable_maps(db, item.ingredient_id) if r.kroger_upc == new_upc),
            None,
        )
        qty, estimated = compute_purchase_qty(
            item.total_qty, item.total_unit, new_row.package_size if new_row else None
        )
        item.purchase_qty = qty
        item.purchase_qty_estimated = estimated
    db.flush()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_matching_multi_upc.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/matching/service.py backend/app/matching/schemas.py backend/tests/test_matching_multi_upc.py
git commit -m "feat(matching): add/remove/switch acceptable products"
```

---

## Task 7: Assemble alternatives + insight in match state

**Files:**
- Modify: `backend/app/matching/schemas.py` (Alternative, ItemInsight, MatchItemRead fields)
- Modify: `backend/app/matching/service.py` (`get_match_state` builds alternatives + insight; new pure helper `_build_alternatives`)
- Test: `backend/tests/test_matching_multi_upc.py` (extend)

**Interfaces:**
- Consumes: `price_cache.get_prices`, `pricing.effective_cents/is_on_sale/unit_price`, `_acceptable_maps`.
- Produces:
  - `Alternative(upc, description, size, regular, promo, effective, unit_price, unit_label, on_sale, stock_level, is_current, price_as_of)` — money fields are dollar floats.
  - `ItemInsight(cheaper_delta_cents: int | None, on_sale: bool, default_out_of_stock: bool)`.
  - `MatchItemRead` gains `alternatives: list[Alternative] = []` and `insight: ItemInsight | None = None`.
  - `get_match_state(db, client: KrogerClient | None = None, *, now: datetime | None = None) -> MatchRead`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_matching_multi_upc.py`:

```python
from app.models import PriceCache


def _seed_prices(db, loc, now, rows):
    for upc, reg, promo, size, stock in rows:
        db.add(PriceCache(kroger_upc=upc, location_id=loc, regular_cents=reg,
                          promo_cents=promo, size_text=size, stock_level=stock, fetched_at=now))
    db.flush()


def test_single_upc_item_has_no_alternatives(db_session):
    gl, ing, item = _draft_with_item(db_session)
    db_session.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="ONLY",
                                        kroger_description="Only", package_size="1 ct", is_default=True))
    db_session.flush()
    read = service.get_match_state(db_session)
    assert read.items[0].alternatives == []
    assert read.items[0].insight is None


def test_multi_upc_item_builds_alternatives_and_cheaper_delta(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    now = datetime.now(timezone.utc)
    # current REG effective 549; ORG on sale at 429 -> cheaper by 120 cents
    _seed_prices(db_session, "L1", now, [
        ("REG", 549, None, "32 fl oz", "HIGH"),
        ("ORG", 599, 429, "25 fl oz", "HIGH"),
    ])
    read = service.get_match_state(db_session, client=None, now=now)
    mi = read.items[0]
    assert {a.upc for a in mi.alternatives} == {"REG", "ORG"}
    cur = next(a for a in mi.alternatives if a.upc == "REG")
    org = next(a for a in mi.alternatives if a.upc == "ORG")
    assert cur.is_current is True
    assert org.effective == 4.29
    assert org.on_sale is True
    assert org.unit_price is not None  # 4.29 / 25
    assert mi.insight.cheaper_delta_cents == 120
    assert mi.insight.on_sale is True
    assert mi.insight.default_out_of_stock is False


def test_insight_flags_default_out_of_stock(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    now = datetime.now(timezone.utc)
    _seed_prices(db_session, "L1", now, [
        ("REG", 549, None, "32 fl oz", "TEMPORARILY_OUT_OF_STOCK"),
        ("ORG", 549, None, "25 fl oz", "HIGH"),
    ])
    read = service.get_match_state(db_session, client=None, now=now)
    assert read.items[0].insight.default_out_of_stock is True
    assert read.items[0].insight.cheaper_delta_cents is None  # equal price, none cheaper


def test_alternatives_present_without_prices_when_no_store(db_session):
    gl, ing, item = _draft_with_item(db_session, store=None)
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    read = service.get_match_state(db_session, client=None)
    mi = read.items[0]
    assert {a.upc for a in mi.alternatives} == {"REG", "ORG"}
    assert all(a.effective is None for a in mi.alternatives)
    assert mi.insight.on_sale is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_matching_multi_upc.py -k "alternatives or insight or single_upc" -v`
Expected: FAIL (`MatchItemRead` has no `alternatives`; `get_match_state` takes no `now`).

- [ ] **Step 3: Add the response schemas**

In `backend/app/matching/schemas.py`, add `from datetime import datetime` at the top and these models (before `MatchItemRead`):

```python
class Alternative(BaseModel):
    upc: str
    description: str
    size: str | None = None
    regular: float | None = None
    promo: float | None = None
    effective: float | None = None
    unit_price: float | None = None
    unit_label: str | None = None
    on_sale: bool = False
    stock_level: str | None = None
    is_current: bool = False
    price_as_of: datetime | None = None


class ItemInsight(BaseModel):
    cheaper_delta_cents: int | None = None
    on_sale: bool = False
    default_out_of_stock: bool = False
```

Extend `MatchItemRead` with two fields:

```python
class MatchItemRead(BaseModel):
    item_id: int
    ingredient_id: int
    ingredient_name: str | None
    total_qty: float | None
    total_unit: str | None
    purchase_qty: int
    purchase_qty_estimated: bool
    kroger_upc: str | None
    current: ProductChoice | None
    alternatives: list[Alternative] = []
    insight: ItemInsight | None = None
```

- [ ] **Step 4: Build alternatives + insight in the service**

In `backend/app/matching/service.py`:

Add imports near the top:

```python
from datetime import datetime, timezone

from app.matching import pricing
from app.matching.price_cache import PriceInfo, get_prices
from app.matching.schemas import (
    AddAlternativeRequest,
    Alternative,
    ConfirmRequest,
    ItemInsight,
    MatchItemRead,
    MatchRead,
    ProductChoice,
    SendItemResult,
    SendResult,
    SwitchPickRequest,
)
```

(Keep the single `from datetime import datetime, timezone` — remove the old `from datetime import datetime, timezone` line if duplicated.)

Add two pure helpers (after `_resolve_default_upc`):

```python
def _to_alternative(
    m: IngredientProductMap, current_upc: str | None, price: PriceInfo | None
) -> Alternative:
    reg_c = price.regular_cents if price else None
    promo_c = price.promo_cents if price else None
    size = (price.size_text if price and price.size_text else m.package_size)
    eff_c = pricing.effective_cents(reg_c, promo_c)
    up = pricing.unit_price(eff_c, size)
    return Alternative(
        upc=m.kroger_upc,
        description=m.kroger_description or "",
        size=size,
        regular=None if reg_c is None else reg_c / 100.0,
        promo=None if promo_c is None else promo_c / 100.0,
        effective=None if eff_c is None else eff_c / 100.0,
        unit_price=None if up is None else round(up[0], 4),
        unit_label=None if up is None else up[1],
        on_sale=pricing.is_on_sale(reg_c, promo_c),
        stock_level=price.stock_level if price else None,
        is_current=(m.kroger_upc == current_upc),
        price_as_of=price.fetched_at if price else None,
    )


def _build_insight(alts: list[Alternative]) -> ItemInsight:
    cur = next((a for a in alts if a.is_current), None)
    cheaper = None
    if cur is not None and cur.effective is not None:
        priced = [a for a in alts if not a.is_current and a.effective is not None]
        if priced:
            cheapest = min(priced, key=lambda a: a.effective)
            if cheapest.effective < cur.effective:
                cheaper = round((cur.effective - cheapest.effective) * 100)
    return ItemInsight(
        cheaper_delta_cents=cheaper,
        on_sale=any(a.on_sale for a in alts),
        default_out_of_stock=(cur is not None and cur.stock_level == "TEMPORARILY_OUT_OF_STOCK"),
    )
```

Replace `get_match_state` with a version that enriches multi-UPC items:

```python
def get_match_state(
    db: Session, client: KrogerClient | None = None, *, now: datetime | None = None
) -> MatchRead:
    apply_remembered_products(db)
    draft = get_or_create_draft(db)
    now = now or datetime.now(timezone.utc)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    loc, store_name = settings_service.get_home_store(db)

    items: list[MatchItemRead] = []
    for it in _kept_items(db, draft.id):
        maps = _acceptable_maps(db, it.ingredient_id)
        alternatives: list[Alternative] = []
        insight: ItemInsight | None = None
        if len(maps) >= 2:
            prices: dict[str, PriceInfo] = {}
            if loc is not None:
                prices = get_prices(db, client, [m.kroger_upc for m in maps], loc, now=now)
            alternatives = [_to_alternative(m, it.kroger_upc, prices.get(m.kroger_upc)) for m in maps]
            insight = _build_insight(alternatives)
        items.append(
            MatchItemRead(
                item_id=it.id,
                ingredient_id=it.ingredient_id,
                ingredient_name=ing_by_id[it.ingredient_id].canonical_name,
                total_qty=it.total_qty,
                total_unit=it.total_unit,
                purchase_qty=it.purchase_qty,
                purchase_qty_estimated=it.purchase_qty_estimated,
                kroger_upc=it.kroger_upc,
                current=_current_choice(db, it),
                alternatives=alternatives,
                insight=insight,
            )
        )

    return MatchRead(
        connected=kroger_auth.get_auth(db) is not None,
        store_location_id=loc,
        store_name=store_name,
        items=items,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_matching_multi_upc.py tests/test_matching_service.py -v`
Expected: PASS (existing single-mapping service tests still green — they have ≤1 mapping, so `alternatives == []`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/matching/service.py backend/app/matching/schemas.py backend/tests/test_matching_multi_upc.py
git commit -m "feat(matching): surface alternatives and price insight in match state"
```

---

## Task 8: Router endpoints

**Files:**
- Modify: `backend/app/matching/router.py`
- Test: `backend/tests/test_matching_router.py` (extend)

**Interfaces:**
- Consumes: `service.add_alternative`, `service.switch_pick`, `service.remove_alternative`, `service.get_match_state` (now accepts a client), `AddAlternativeRequest`, `SwitchPickRequest`, `get_kroger_client`.
- Produces HTTP routes:
  - `POST /list/items/{item_id}/alternatives` → `AddAlternativeRequest` → `MatchRead`
  - `POST /list/items/{item_id}/pick` → `SwitchPickRequest` → `MatchRead` (409 on non-acceptable UPC)
  - `DELETE /list/items/{item_id}/alternatives/{upc}` → `MatchRead`
  - `GET /list/match` now passes the Kroger client so prices populate.

- [ ] **Step 1: Write the failing tests**

First inspect `backend/tests/test_matching_router.py` to copy its app/client fixture pattern, then append tests modeled on it. The tests below assume a FastAPI `TestClient` named `client` and a way to seed a draft item with two mappings (reuse the existing helpers in that file; if it seeds via the DB session fixture, follow that pattern). Add:

```python
def test_add_alternative_endpoint_adds_mapping(client, seeded_two_upc_item):
    item_id = seeded_two_upc_item
    resp = client.post(f"/list/items/{item_id}/alternatives",
                       json={"kroger_upc": "VAN", "kroger_description": "Vanilla", "package_size": "32 fl oz"})
    assert resp.status_code == 200
    body = resp.json()
    alts = body["items"][0]["alternatives"]
    assert "VAN" in {a["upc"] for a in alts}


def test_switch_pick_endpoint_changes_current(client, seeded_two_upc_item):
    item_id = seeded_two_upc_item
    resp = client.post(f"/list/items/{item_id}/pick", json={"kroger_upc": "ORG"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["kroger_upc"] == "ORG"


def test_switch_pick_endpoint_rejects_bad_upc(client, seeded_two_upc_item):
    item_id = seeded_two_upc_item
    resp = client.post(f"/list/items/{item_id}/pick", json={"kroger_upc": "NOPE"})
    assert resp.status_code == 409


def test_remove_alternative_endpoint(client, seeded_two_upc_item):
    item_id = seeded_two_upc_item
    resp = client.delete(f"/list/items/{item_id}/alternatives/ORG")
    assert resp.status_code == 200
    assert "ORG" not in {a["upc"] for a in resp.json()["items"][0]["alternatives"]}
```

If `test_matching_router.py` does not already provide a `seeded_two_upc_item` fixture, add one in that file mirroring its existing item-seeding pattern: create an ingredient, a draft grocery list with `store_location_id="L1"`, a `GroceryListItem` (`kroger_upc="REG"`), and two `IngredientProductMap` rows (`REG` is_default, `ORG`), then `yield item.id`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_matching_router.py -k "alternative or switch_pick or pick" -v`
Expected: FAIL (routes return 404 / fixtures missing).

- [ ] **Step 3: Implement the routes**

In `backend/app/matching/router.py`, extend imports:

```python
from app.matching.schemas import (
    AddAlternativeRequest,
    ConfirmRequest,
    MatchRead,
    ProductChoice,
    SendRequest,
    SendResult,
    SetStoreRequest,
    SwitchPickRequest,
)
```

Pass the client into `get_match` so prices populate:

```python
@router.get("/match", response_model=MatchRead)
def get_match(
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    state = service.get_match_state(db, kroger)
    db.commit()
    return state
```

Add the three new routes (after `confirm_product`):

```python
@router.post("/items/{item_id}/alternatives", response_model=MatchRead)
def add_alternative(
    item_id: int,
    body: AddAlternativeRequest,
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        service.add_alternative(db, item_id, body)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    state = service.get_match_state(db, kroger)
    db.commit()
    return state


@router.post("/items/{item_id}/pick", response_model=MatchRead)
def switch_pick(
    item_id: int,
    body: SwitchPickRequest,
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        service.switch_pick(db, item_id, body.kroger_upc)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.UpcNotAcceptableError as exc:
        raise HTTPException(status_code=409, detail={"error": "bad_upc", "message": str(exc)})
    state = service.get_match_state(db, kroger)
    db.commit()
    return state


@router.delete("/items/{item_id}/alternatives/{upc}", response_model=MatchRead)
def remove_alternative(
    item_id: int,
    upc: str,
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        service.remove_alternative(db, item_id, upc)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    state = service.get_match_state(db, kroger)
    db.commit()
    return state
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_matching_router.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole backend suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add backend/app/matching/router.py backend/tests/test_matching_router.py
git commit -m "feat(matching): endpoints for add/remove/switch alternatives"
```

---

## Task 9: Frontend types + API client

**Files:**
- Modify: `frontend/src/recipes/types.ts`
- Modify: `frontend/src/api.ts`
- Test: covered by Task 10 (CartTab) — no standalone test for thin fetch wrappers, matching the existing `api.ts` (which has none of its own).

**Interfaces:**
- Produces: `Alternative`, `ItemInsight` types; `ProductChoice.promo`; `MatchItem.alternatives` + `.insight`; `addAlternative`, `switchPick`, `removeAlternative` functions returning `MatchData`.

- [ ] **Step 1: Extend the types**

In `frontend/src/recipes/types.ts`, add `promo` to `ProductChoice`:

```typescript
export interface ProductChoice {
  upc: string;
  description: string;
  size: string | null;
  price: number | null;
  promo?: number | null;
  stock_level: string | null;
  brand?: string | null;
  image_url?: string | null;
}
```

Add the new interfaces (after `ProductChoice`):

```typescript
export interface Alternative {
  upc: string;
  description: string;
  size: string | null;
  regular: number | null;
  promo: number | null;
  effective: number | null;
  unit_price: number | null;
  unit_label: string | null;
  on_sale: boolean;
  stock_level: string | null;
  is_current: boolean;
  price_as_of: string | null;
}

export interface ItemInsight {
  cheaper_delta_cents: number | null;
  on_sale: boolean;
  default_out_of_stock: boolean;
}
```

Extend `MatchItem`:

```typescript
export interface MatchItem {
  item_id: number;
  ingredient_id: number;
  ingredient_name: string | null;
  total_qty: number | null;
  total_unit: string | null;
  purchase_qty: number;
  purchase_qty_estimated: boolean;
  kroger_upc: string | null;
  current: ProductChoice | null;
  alternatives: Alternative[];
  insight: ItemInsight | null;
}
```

- [ ] **Step 2: Add the API functions**

In `frontend/src/api.ts`, after `confirmProduct`, add:

```typescript
export async function addAlternative(
  itemId: number,
  body: ConfirmProductBody,
): Promise<MatchData> {
  const res = await fetch(`${BASE_URL}/list/items/${itemId}/alternatives`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<MatchData>(res);
}

export async function switchPick(itemId: number, upc: string): Promise<MatchData> {
  const res = await fetch(`${BASE_URL}/list/items/${itemId}/pick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kroger_upc: upc }),
  });
  return json<MatchData>(res);
}

export async function removeAlternative(itemId: number, upc: string): Promise<MatchData> {
  const res = await fetch(
    `${BASE_URL}/list/items/${itemId}/alternatives/${encodeURIComponent(upc)}`,
    { method: "DELETE" },
  );
  return json<MatchData>(res);
}
```

`ConfirmProductBody` is already imported in `api.ts`; no new import needed.

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc -b`
Expected: no type errors. (CartTab still compiles because the new `MatchItem` fields are required only in data it constructs in Task 10; existing test fixtures are updated there.)

> Note: if `tsc` reports that existing `baseMatch` test fixtures lack `alternatives`/`insight`, that is fixed in Task 10 Step 1. It is acceptable for this step to leave `CartTab.test.tsx` type-erroring until Task 10; run `npx tsc -b` again at the end of Task 10.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/recipes/types.ts frontend/src/api.ts
git commit -m "feat(web): types and API client for multi-UPC alternatives"
```

---

## Task 10: Cart tab — badges + inline comparison

**Files:**
- Modify: `frontend/src/recipes/CartTab.tsx`
- Modify: `frontend/src/recipes/ProductPickerModal.tsx` (title/CTA configurable for "add alternative")
- Test: `frontend/src/recipes/CartTab.test.tsx`

**Interfaces:**
- Consumes: `switchPick`, `removeAlternative`, `addAlternative`, `getMatch`; `Alternative`, `ItemInsight`, `MatchItem`.

- [ ] **Step 1: Update existing fixtures and write failing tests**

In `frontend/src/recipes/CartTab.test.tsx`, update `baseMatch` so both items satisfy the new required fields, and add a multi-UPC item:

```typescript
const baseMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    { item_id: 1, ingredient_id: 2, ingredient_name: "flour", total_qty: 3, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: "0001", current: { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" }, alternatives: [], insight: null },
    { item_id: 2, ingredient_id: 3, ingredient_name: "milk", total_qty: 1, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: null, current: null, alternatives: [], insight: null },
  ],
};

const multiMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    {
      item_id: 5, ingredient_id: 9, ingredient_name: "creamer",
      total_qty: 1, total_unit: "bottle", purchase_qty: 1, purchase_qty_estimated: false,
      kroger_upc: "REG",
      current: { upc: "REG", description: "Califia Regular", size: "32 fl oz", price: 5.49, stock_level: "HIGH" },
      alternatives: [
        { upc: "REG", description: "Califia Regular", size: "32 fl oz", regular: 5.49, promo: null, effective: 5.49, unit_price: 0.17, unit_label: "fl oz", on_sale: false, stock_level: "HIGH", is_current: true, price_as_of: "2026-06-27T10:00:00Z" },
        { upc: "ORG", description: "Califia Organic", size: "25 fl oz", regular: 5.99, promo: 4.29, effective: 4.29, unit_price: 0.17, unit_label: "fl oz", on_sale: true, stock_level: "HIGH", is_current: false, price_as_of: "2026-06-27T10:00:00Z" },
      ],
      insight: { cheaper_delta_cents: 120, on_sale: true, default_out_of_stock: false },
    },
  ],
};
```

Add these tests inside `describe("CartTab", ...)`:

```typescript
it("shows a cheaper-alt badge for a multi-UPC item", async () => {
  vi.spyOn(api, "getMatch").mockResolvedValue(multiMatch);
  render(<CartTab />);
  expect(await screen.findByText(/\$1\.20 cheaper/i)).toBeInTheDocument();
  expect(screen.getByText(/on sale/i)).toBeInTheDocument();
});

it("expands the comparison and switches the pick", async () => {
  vi.spyOn(api, "getMatch").mockResolvedValue(multiMatch);
  const sw = vi.spyOn(api, "switchPick").mockResolvedValue(multiMatch);
  render(<CartTab />);
  await screen.findByText(/\$1\.20 cheaper/i);
  await userEvent.click(screen.getByRole("button", { name: /compare/i }));
  expect(await screen.findByText(/Califia Organic/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /use this/i }));
  await waitFor(() => expect(sw).toHaveBeenCalledWith(5, "ORG"));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- CartTab`
Expected: FAIL (no cheaper badge / compare button rendered).

- [ ] **Step 3: Make the picker support an "add alternative" mode**

In `frontend/src/recipes/ProductPickerModal.tsx`, accept optional `title` and `chooseLabel` props and use them (defaults preserve current behavior):

```typescript
export function ProductPickerModal({
  itemId,
  ingredientName,
  onChoose,
  onClose,
  title = "Choose a product",
  chooseLabel = "Choose",
}: {
  itemId: number;
  ingredientName: string | null;
  onChoose: (product: ProductChoice) => void | Promise<void>;
  onClose: () => void;
  title?: string;
  chooseLabel?: string;
}) {
```

Then use them: change `<Modal title="Choose a product"` to `<Modal title={title}` and the choose button text `Choose` to `{chooseLabel}`.

- [ ] **Step 4: Implement badges + comparison in CartTab**

In `frontend/src/recipes/CartTab.tsx`:

Update the import line:

```typescript
import { ApiError, addAlternative, confirmProduct, getMatch, removeAlternative, sendCart, setPantryDecision, switchPick } from "../api";
```

```typescript
import type { Alternative, MatchData, MatchItem, ProductChoice, SendResult } from "./types";
```

Add expansion + picker-mode state inside the component (with the other `useState` calls):

```typescript
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [pickerMode, setPickerMode] = useState<"confirm" | "alternative">("confirm");

  function toggleExpand(itemId: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(itemId) ? next.delete(itemId) : next.add(itemId);
      return next;
    });
  }

  async function choosePick(itemId: number, upc: string) {
    setError(null);
    try {
      setMatch(await switchPick(itemId, upc));
    } catch (err) {
      report(err);
    }
  }

  async function dropAlternative(itemId: number, upc: string) {
    setError(null);
    try {
      setMatch(await removeAlternative(itemId, upc));
    } catch (err) {
      report(err);
    }
  }
```

Change `pick` so that, in "alternative" mode, a chosen product is added as an alternative rather than confirmed:

```typescript
  async function pick(product: ProductChoice) {
    if (openItem === null) return;
    setError(null);
    try {
      const body = {
        kroger_upc: product.upc,
        kroger_description: product.description,
        package_size: product.size,
      };
      setMatch(
        pickerMode === "alternative"
          ? await addAlternative(openItem.item_id, body)
          : await confirmProduct(openItem.item_id, body),
      );
    } catch (err) {
      report(err);
    } finally {
      setOpenItem(null);
      setPickerMode("confirm");
    }
  }
```

Add helpers above `row` for formatting and badges:

```typescript
  function money(n: number | null): string {
    return n == null ? "—" : `$${n.toFixed(2)}`;
  }

  function badges(it: MatchItem) {
    const ins = it.insight;
    if (!ins) return null;
    return (
      <div className="flex flex-wrap items-center gap-2">
        {ins.cheaper_delta_cents != null && (
          <Pill tone="success">↓ ${(ins.cheaper_delta_cents / 100).toFixed(2)} cheaper alt</Pill>
        )}
        {ins.on_sale && <Pill tone="warning">on sale</Pill>}
        {ins.default_out_of_stock && <Pill tone="danger">default out of stock</Pill>}
        <Button variant="link" className="px-0" onClick={() => toggleExpand(it.item_id)}>
          {expanded.has(it.item_id) ? "Hide" : "Compare"}
        </Button>
      </div>
    );
  }

  function altRow(it: MatchItem, a: Alternative) {
    return (
      <li key={a.upc} className="flex items-center gap-3 rounded-xl border border-line p-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm text-ink">
            {a.description}
            {a.is_current && <span className="ml-2 text-xs font-semibold text-success">current</span>}
            {a.stock_level === "TEMPORARILY_OUT_OF_STOCK" && <Pill tone="danger">Out of stock</Pill>}
          </p>
          <p className="text-xs text-muted">
            {a.size}
            {a.effective != null && (
              <>
                {" · "}
                {a.on_sale ? (
                  <>
                    <span className="font-semibold text-warning">{money(a.effective)}</span>{" "}
                    <span className="line-through">{money(a.regular)}</span>
                  </>
                ) : (
                  money(a.effective)
                )}
                {a.unit_price != null && a.unit_label && ` · $${a.unit_price.toFixed(2)}/${a.unit_label}`}
              </>
            )}
            {a.effective == null && " · price unavailable"}
          </p>
        </div>
        {!a.is_current && (
          <Button variant="secondary" onClick={() => choosePick(it.item_id, a.upc)}>
            Use this
          </Button>
        )}
        <button
          type="button"
          aria-label={`Remove ${a.description}`}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-danger"
          onClick={() => dropAlternative(it.item_id, a.upc)}
        >
          <TrashIcon size={16} />
        </button>
      </li>
    );
  }
```

In `row`, after the `<Button variant="link" ...>{it.current ? "Change" : "Choose product →"}</Button>`, add the badges and the expanded comparison (still inside the `<div className="min-w-0">`):

```typescript
          {badges(it)}
          {expanded.has(it.item_id) && it.alternatives.length > 0 && (
            <div className="mt-2 flex flex-col gap-2">
              <ul className="flex flex-col gap-2">
                {it.alternatives.map((a) => altRow(it, a))}
              </ul>
              <Button
                variant="link"
                className="px-0"
                onClick={() => {
                  setPickerMode("alternative");
                  setOpenItem(it);
                }}
              >
                + find similar…
              </Button>
              {it.alternatives.some((a) => a.price_as_of) && (
                <p className="text-xs text-muted">prices updated recently</p>
              )}
            </div>
          )}
```

Finally, pass the picker mode props where `ProductPickerModal` is rendered:

```typescript
      {openItem && (
        <ProductPickerModal
          key={`${openItem.item_id}-${pickerMode}`}
          itemId={openItem.item_id}
          ingredientName={openItem.ingredient_name}
          onChoose={pick}
          onClose={() => {
            setOpenItem(null);
            setPickerMode("confirm");
          }}
          title={pickerMode === "alternative" ? "Add an alternative" : "Choose a product"}
          chooseLabel={pickerMode === "alternative" ? "Add as alternative" : "Choose"}
        />
      )}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test -- CartTab`
Expected: PASS.

- [ ] **Step 6: Typecheck and run the full frontend suite**

Run: `cd frontend && npx tsc -b && npm test`
Expected: no type errors; all tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/recipes/CartTab.tsx frontend/src/recipes/ProductPickerModal.tsx frontend/src/recipes/CartTab.test.tsx
git commit -m "feat(web): multi-UPC price-insight badges and inline comparison in Cart"
```

---

## Final verification

- [ ] **Backend:** `cd backend && uv run pytest -q` → all pass.
- [ ] **Frontend:** `cd frontend && npx tsc -b && npm test` → typecheck clean, all pass.
- [ ] **Migration:** `cd backend && uv run alembic upgrade head` applies `price_cache` (dev Postgres up).
- [ ] **Manual smoke (optional, needs Kroger creds + store):** add a second acceptable product to an ingredient via "find similar", confirm the badge appears on the Cart row, expand, and switch — verify the row's product changes and no purchase-log row is written until "Send to cart".

---

## Spec coverage check

| Spec requirement | Task |
| --- | --- |
| Multiple acceptable UPCs per ingredient | 5, 6 |
| Default = last-purchased → is_default → first | 5 |
| Switching never rewrites purchase history | 6 |
| 12h price cache, multi-UPC only | 3, 4, 7 |
| Effective price / on-sale semantics | 2, 7 |
| Sticker + unit price, degrade when unparseable | 2, 7, 10 |
| `locationId` required; no store → no insights | 4, 7, 10 |
| Inline badge + expand in Cart; picker for adding | 10 |
| Out-of-stock surfaced, never auto-switched | 7, 10 |
| Add/remove/switch endpoints | 8 |
| Kroger promo + by-UPC detail | 1 |

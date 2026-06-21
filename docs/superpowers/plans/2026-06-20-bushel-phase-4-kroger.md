# Phase 4: Kroger Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect a Kroger account, pick a store, match each consolidated grocery-list item to a Kroger product (confirm-once → remembered), translate totals into package quantities, and push the items to the user's Kroger cart (write-only), recording what was sent.

**Architecture:** Two new backend modules. `app/kroger/` is the only module doing network I/O to Kroger (OAuth, locations, products, cart add) — tested against mocked `httpx` transports. `app/matching/` is pure app logic + DB (product confirm/persist, `purchase_qty` translation, send orchestration), calling `kroger/` for network and `consolidate/units.py` for unit math. Functional React screens drive the flow.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, `httpx`, `pint` (via `consolidate/units.py`), React/TS + Vite, pytest, vitest.

**Spec:** `docs/superpowers/specs/2026-06-20-bushel-phase-4-kroger-design.md`

**Conventions to follow (from the existing codebase):**
- All backend commands run from `backend/` with `uv run …`. Tests need a reachable Postgres (the session fixture creates/drops tables on `get_settings().database_url`).
- Routers are thin and delegate to a `service.py`; services are the only DB writers; `from __future__ import annotations` at the top of modules.
- Single pint importer is `consolidate/units.py` — `matching/` must NOT import pint; it calls a helper there.
- Frontend: fetch helpers live in `frontend/src/api.ts`, types in `frontend/src/recipes/types.ts`, screens are components under `frontend/src/recipes/`, tests are `*.test.tsx`/`*.test.ts` (vitest).
- **Local run gotcha:** `docker stop bushel-pg` before `docker compose up` (host port 5432 conflict).

**Endpoint summary (note: refines the spec — product search is a dedicated per-item endpoint to bound Kroger API calls, instead of `GET /list/match?q=`):**
- `GET /kroger/status` · `GET /kroger/login` · `GET /auth/callback` · `GET /kroger/locations?zip=`
- `GET /list/match` (DB-only overview) · `GET /list/items/{item_id}/products?q=` (live search) · `POST /list/items/{item_id}/product` (confirm) · `POST /list/send`

---

## Task 1: Migration — `grocery_list_items.purchase_qty_estimated`

**Files:**
- Modify: `backend/app/models.py:80-92` (GroceryListItem)
- Create: `backend/migrations/versions/<rev>_add_purchase_qty_estimated.py`
- Test: `backend/tests/test_models.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_models.py`:

```python
def test_grocery_list_item_has_purchase_qty_estimated_default_false(db_session):
    from app.models import GroceryList, GroceryListItem, Ingredient

    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(ing)
    db_session.flush()
    gl = GroceryList(name="Draft", status="draft")
    db_session.add(gl)
    db_session.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id)
    db_session.add(item)
    db_session.flush()
    assert item.purchase_qty_estimated is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::test_grocery_list_item_has_purchase_qty_estimated_default_false -v`
Expected: FAIL — `TypeError`/`AttributeError`: `purchase_qty_estimated` is not a column.

- [ ] **Step 3: Add the column to the model**

In `backend/app/models.py`, inside `class GroceryListItem`, add after the `purchase_qty` line:

```python
    purchase_qty_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

(`Boolean` is already imported in this file.)

- [ ] **Step 4: Create the Alembic migration**

Create `backend/migrations/versions/c1a2b3c4d5e6_add_purchase_qty_estimated.py`:

```python
"""add purchase_qty_estimated to grocery_list_items

Revision ID: c1a2b3c4d5e6
Revises: 0cff1d550060
Create Date: 2026-06-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '0cff1d550060'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'grocery_list_items',
        sa.Column('purchase_qty_estimated', sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('grocery_list_items', 'purchase_qty_estimated')
```

- [ ] **Step 5: Apply the migration and run the test**

Run:
```bash
uv run alembic upgrade head
uv run pytest tests/test_models.py::test_grocery_list_item_has_purchase_qty_estimated_default_false -v
```
Expected: migration applies cleanly; test PASSES.

- [ ] **Step 6: Commit**

```bash
git add app/models.py migrations/versions/c1a2b3c4d5e6_add_purchase_qty_estimated.py tests/test_models.py
git commit -m "feat(db): add grocery_list_items.purchase_qty_estimated"
```

---

## Task 2: `units.convert_qty` helper (keep pint isolated)

**Files:**
- Modify: `backend/app/consolidate/units.py` (append function)
- Test: `backend/tests/test_units.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_units.py`:

```python
from app.consolidate.units import convert_qty


def test_convert_qty_compatible_units():
    # 3 cups -> ounces (volume). 1 cup = 8 fl oz, pint treats "ounce" as fluid here via volume dim.
    assert convert_qty(2, "lb", "oz") == 32.0


def test_convert_qty_same_unit_passthrough():
    assert convert_qty(5, "bag", "bag") == 5


def test_convert_qty_incompatible_returns_none():
    assert convert_qty(2, "cup", "lb") is None


def test_convert_qty_unparseable_unit_returns_none():
    assert convert_qty(2, "clove", "lb") is None


def test_convert_qty_none_unit_returns_none():
    assert convert_qty(2, None, "lb") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_units.py -k convert_qty -v`
Expected: FAIL — `ImportError: cannot import name 'convert_qty'`.

- [ ] **Step 3: Implement `convert_qty`**

Append to `backend/app/consolidate/units.py`:

```python
def convert_qty(qty: float, from_unit: str | None, to_unit: str | None) -> float | None:
    """Convert qty from one unit to another. Returns None when units are missing,
    unparseable by pint, or dimensionally incompatible. Same normalized unit passes through."""
    fu = _normalize_unit(from_unit)
    tu = _normalize_unit(to_unit)
    if fu is None or tu is None:
        return None
    if fu == tu:
        return qty
    try:
        return (qty * _ureg(fu)).to(_ureg(tu)).magnitude
    except Exception:  # noqa: BLE001 — pint raises several types for non-units / bad conversions
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_units.py -k convert_qty -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add app/consolidate/units.py tests/test_units.py
git commit -m "feat(units): add convert_qty helper for cross-unit conversion"
```

---

## Task 3: `matching/purchase.py` — total → purchase_qty

**Files:**
- Create: `backend/app/matching/__init__.py` (empty)
- Create: `backend/app/matching/purchase.py`
- Test: `backend/tests/test_purchase.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_purchase.py`:

```python
from app.matching.purchase import compute_purchase_qty, parse_package_size


def test_parse_package_size_number_and_unit():
    assert parse_package_size("5 lb") == (5.0, "lb")
    assert parse_package_size("16.9 fl oz") == (16.9, "fl oz")
    assert parse_package_size("6 ct") == (6.0, "ct")


def test_parse_package_size_no_number_returns_none():
    assert parse_package_size("each") is None
    assert parse_package_size(None) is None
    assert parse_package_size("") is None


def test_compute_purchase_qty_compatible_ceils():
    # need 3 lb, package is 1 lb -> 3 packages, not estimated
    assert compute_purchase_qty(3.0, "lb", "1 lb") == (3, False)
    # need 2.5 lb, package 1 lb -> ceil 3
    assert compute_purchase_qty(2.5, "lb", "1 lb") == (3, False)
    # need 32 oz, package 1 lb (16 oz) -> 2
    assert compute_purchase_qty(32.0, "oz", "1 lb") == (2, False)


def test_compute_purchase_qty_total_none_is_estimated_one():
    assert compute_purchase_qty(None, None, "5 lb") == (1, True)


def test_compute_purchase_qty_incompatible_units_estimated_one():
    # need 3 cups (volume) but package is in lb (mass) -> can't convert
    assert compute_purchase_qty(3.0, "cup", "5 lb") == (1, True)


def test_compute_purchase_qty_unparseable_package_estimated_one():
    assert compute_purchase_qty(3.0, "lb", "each") == (1, True)
    assert compute_purchase_qty(3.0, "lb", None) == (1, True)


def test_compute_purchase_qty_floor_is_at_least_one():
    # need 0.1 lb, package 5 lb -> ceil(0.02)=1
    assert compute_purchase_qty(0.1, "lb", "5 lb") == (1, False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_purchase.py -v`
Expected: FAIL — `ModuleNotFoundError: app.matching.purchase`.

- [ ] **Step 3: Create the module**

Create `backend/app/matching/__init__.py` (empty file).

Create `backend/app/matching/purchase.py`:

```python
"""Translate a consolidated total into a number of packages to buy.

No pint import here — unit math goes through consolidate.units.convert_qty so pint
stays isolated to one module.
"""

from __future__ import annotations

import math
import re

from app.consolidate.units import convert_qty

_PKG_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(.*?)\s*$")


def parse_package_size(text: str | None) -> tuple[float, str] | None:
    """Parse a Kroger package_size string like '5 lb' / '16.9 fl oz' / '6 ct'.

    Returns (qty, unit_text) or None when there is no leading number."""
    if not text:
        return None
    m = _PKG_RE.match(text)
    if not m:
        return None
    qty = float(m.group(1))
    unit = m.group(2).strip() or None
    if unit is None:
        return None
    return qty, unit


def compute_purchase_qty(
    total_qty: float | None, total_unit: str | None, package_size: str | None
) -> tuple[int, bool]:
    """Return (purchase_qty, estimated). estimated=True means we fell back to 1 because
    the total is unknown or units could not be reconciled — the UI should flag it."""
    if total_qty is None:
        return 1, True
    parsed = parse_package_size(package_size)
    if parsed is None:
        return 1, True
    pkg_qty, pkg_unit = parsed
    if pkg_qty <= 0:
        return 1, True
    converted = convert_qty(total_qty, total_unit, pkg_unit)
    if converted is None:
        return 1, True
    return max(math.ceil(converted / pkg_qty), 1), False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_purchase.py -v`
Expected: PASS (all cases).

- [ ] **Step 5: Commit**

```bash
git add app/matching/__init__.py app/matching/purchase.py tests/test_purchase.py
git commit -m "feat(matching): purchase_qty translation from package_size"
```

---

## Task 4: `kroger/schemas.py` — typed wrappers + API models

**Files:**
- Create: `backend/app/kroger/__init__.py` (empty)
- Create: `backend/app/kroger/schemas.py`
- Test: `backend/tests/test_kroger_schemas.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kroger_schemas.py`:

```python
from app.kroger.schemas import Location, Product, TokenResp


def test_token_resp_defaults():
    t = TokenResp(access_token="a", expires_in=1800)
    assert t.refresh_token is None
    assert t.scope == ""


def test_product_and_location_construct():
    p = Product(upc="0001", description="Flour", size="5 lb", price=3.49, stock_level="HIGH")
    assert p.upc == "0001"
    loc = Location(location_id="L1", name="Store", address="1 Main St")
    assert loc.location_id == "L1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kroger_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: app.kroger.schemas`.

- [ ] **Step 3: Create the schemas**

Create `backend/app/kroger/__init__.py` (empty file).

Create `backend/app/kroger/schemas.py`:

```python
"""Typed wrappers over the Kroger JSON we consume, plus API request/response models."""

from __future__ import annotations

from pydantic import BaseModel


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    scope: str = ""


class Location(BaseModel):
    location_id: str
    name: str
    address: str


class Product(BaseModel):
    upc: str
    description: str
    size: str | None = None
    price: float | None = None
    stock_level: str | None = None


class KrogerStatus(BaseModel):
    connected: bool
    expired: bool


class LoginUrl(BaseModel):
    url: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kroger_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kroger/__init__.py app/kroger/schemas.py tests/test_kroger_schemas.py
git commit -m "feat(kroger): typed schemas for tokens, products, locations"
```

---

## Task 5: `kroger/client.py` — token methods

**Files:**
- Create: `backend/app/kroger/client.py`
- Test: `backend/tests/test_kroger_client_auth.py`

The client uses an injectable `httpx.Client` so tests drive it with `httpx.MockTransport`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kroger_client_auth.py`:

```python
import base64

import httpx
import pytest

from app.kroger.client import KrogerAuthError, KrogerClient


def _client(handler):
    http = httpx.Client(base_url="https://api.kroger.com", transport=httpx.MockTransport(handler))
    return KrogerClient(http=http, client_id="cid", client_secret="secret",
                        redirect_uri="http://localhost:8000/auth/callback")


def test_fetch_client_token_uses_basic_auth_and_client_credentials():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 1800, "token_type": "bearer"})

    token = _client(handler).fetch_client_token()
    assert token.access_token == "tok"
    expected = "Basic " + base64.b64encode(b"cid:secret").decode()
    assert seen["auth"] == expected
    assert "grant_type=client_credentials" in seen["body"]


def test_exchange_code_returns_refresh_token():
    def handler(request):
        assert "grant_type=authorization_code" in request.content.decode()
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 1800})

    token = _client(handler).exchange_code("the-code")
    assert token.refresh_token == "r"


def test_refresh_uses_refresh_grant():
    def handler(request):
        assert "grant_type=refresh_token" in request.content.decode()
        return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 1800})

    token = _client(handler).refresh("r")
    assert token.access_token == "a2"


def test_token_401_raises_auth_error():
    def handler(request):
        return httpx.Response(401, json={"error": "invalid_client"})

    with pytest.raises(KrogerAuthError):
        _client(handler).fetch_client_token()


def test_authorize_url_includes_scopes_and_state():
    url = _client(lambda r: httpx.Response(200, json={})).authorize_url("xyz")
    assert "response_type=code" in url
    assert "state=xyz" in url
    assert "cart.basic" in url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kroger_client_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: app.kroger.client`.

- [ ] **Step 3: Implement the client skeleton + token methods**

Create `backend/app/kroger/client.py`:

```python
"""The only module that performs network I/O to Kroger. No DB access here.

Tests inject an httpx.Client backed by httpx.MockTransport, so request building is
exercised without real network calls.
"""

from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.kroger.schemas import TokenResp

PROD_BASE = "https://api.kroger.com"
_SCOPES = "product.compact cart.basic:write profile.compact"


class KrogerError(Exception):
    """Any Kroger API failure."""


class KrogerAuthError(KrogerError):
    """401/403 — credentials or token rejected; caller should re-auth."""


class KrogerUnavailableError(KrogerError):
    """429/5xx — transient; caller should surface 'try later'."""


class KrogerClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        *,
        base_url: str = PROD_BASE,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        s = get_settings()
        self._base = base_url
        self._http = http or httpx.Client(base_url=base_url, timeout=10.0)
        self._client_id = client_id if client_id is not None else s.kroger_client_id
        self._client_secret = client_secret if client_secret is not None else s.kroger_client_secret
        self._redirect_uri = redirect_uri if redirect_uri is not None else s.kroger_redirect_uri

    # --- helpers -------------------------------------------------------------
    def _basic_auth(self) -> str:
        raw = f"{self._client_id}:{self._client_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code in (401, 403):
            raise KrogerAuthError(f"Kroger auth failed: {resp.status_code} {resp.text}")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise KrogerUnavailableError(f"Kroger unavailable: {resp.status_code}")
        if resp.status_code >= 400:
            raise KrogerError(f"Kroger error: {resp.status_code} {resp.text}")

    def _token_request(self, data: dict[str, str]) -> TokenResp:
        resp = self._http.post(
            "/v1/connect/oauth2/token",
            data=data,
            headers={
                "Authorization": self._basic_auth(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        self._raise_for_status(resp)
        return TokenResp(**resp.json())

    # --- auth ----------------------------------------------------------------
    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "scope": _SCOPES,
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "state": state,
            }
        )
        return f"{self._base}/v1/connect/oauth2/authorize?{query}"

    def fetch_client_token(self) -> TokenResp:
        return self._token_request({"grant_type": "client_credentials", "scope": "product.compact"})

    def exchange_code(self, code: str) -> TokenResp:
        return self._token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self._redirect_uri}
        )

    def refresh(self, refresh_token: str) -> TokenResp:
        return self._token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kroger_client_auth.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add app/kroger/client.py tests/test_kroger_client_auth.py
git commit -m "feat(kroger): client OAuth token methods (client-cred, code, refresh)"
```

---

## Task 6: `kroger/client.py` — locations & products search

**Files:**
- Modify: `backend/app/kroger/client.py` (add methods)
- Test: `backend/tests/test_kroger_client_catalog.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kroger_client_catalog.py`:

```python
import httpx

from app.kroger.client import KrogerClient


def _client(handler):
    http = httpx.Client(base_url="https://api.kroger.com", transport=httpx.MockTransport(handler))
    return KrogerClient(http=http, client_id="c", client_secret="s", redirect_uri="u")


def test_search_locations_parses_data():
    def handler(request):
        assert request.url.path == "/v1/locations"
        assert request.url.params["filter.zipCode.near"] == "45202"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"data": [
            {"locationId": "L1", "name": "Kroger Downtown",
             "address": {"addressLine1": "1 Main St", "city": "Cincinnati", "state": "OH", "zipCode": "45202"}},
        ]})

    locs = _client(handler).search_locations("tok", "45202")
    assert locs[0].location_id == "L1"
    assert "1 Main St" in locs[0].address
    assert "Cincinnati" in locs[0].address


def test_search_products_parses_first_item_fields():
    def handler(request):
        assert request.url.path == "/v1/products"
        assert request.url.params["filter.term"] == "flour"
        assert request.url.params["filter.locationId"] == "L1"
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "AP Flour",
             "items": [{"size": "5 lb", "price": {"regular": 3.49}, "inventory": {"stockLevel": "HIGH"}}]},
            {"upc": "0002", "description": "Bread Flour", "items": []},
        ]})

    prods = _client(handler).search_products("tok", "flour", "L1")
    assert prods[0].upc == "0001"
    assert prods[0].size == "5 lb"
    assert prods[0].price == 3.49
    assert prods[0].stock_level == "HIGH"
    # product with empty items still parses with None fields
    assert prods[1].upc == "0002"
    assert prods[1].size is None
    assert prods[1].price is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kroger_client_catalog.py -v`
Expected: FAIL — `AttributeError: 'KrogerClient' object has no attribute 'search_locations'`.

- [ ] **Step 3: Implement the methods**

Add to `backend/app/kroger/client.py` (import `Location, Product` at the top, alongside `TokenResp`):

```python
from app.kroger.schemas import Location, Product, TokenResp
```

Add these methods to `KrogerClient`:

```python
    def search_locations(self, token: str, zip_code: str, limit: int = 10) -> list[Location]:
        resp = self._http.get(
            "/v1/locations",
            params={"filter.zipCode.near": zip_code, "filter.limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        self._raise_for_status(resp)
        out: list[Location] = []
        for row in resp.json().get("data", []):
            addr = row.get("address", {})
            parts = [addr.get("addressLine1"), addr.get("city"), addr.get("state"), addr.get("zipCode")]
            out.append(
                Location(
                    location_id=row["locationId"],
                    name=row.get("name", ""),
                    address=", ".join(p for p in parts if p),
                )
            )
        return out

    def search_products(
        self, token: str, term: str, location_id: str, limit: int = 10
    ) -> list[Product]:
        resp = self._http.get(
            "/v1/products",
            params={"filter.term": term, "filter.locationId": location_id, "filter.limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        self._raise_for_status(resp)
        out: list[Product] = []
        for row in resp.json().get("data", []):
            items = row.get("items") or []
            first = items[0] if items else {}
            price = (first.get("price") or {}).get("regular")
            stock = (first.get("inventory") or {}).get("stockLevel")
            out.append(
                Product(
                    upc=row["upc"],
                    description=row.get("description", ""),
                    size=first.get("size"),
                    price=price,
                    stock_level=stock,
                )
            )
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kroger_client_catalog.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kroger/client.py tests/test_kroger_client_catalog.py
git commit -m "feat(kroger): client locations + products search"
```

---

## Task 7: `kroger/client.py` — cart add (PUT /v1/cart/add)

**Files:**
- Modify: `backend/app/kroger/client.py` (add method)
- Test: `backend/tests/test_kroger_client_cart.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kroger_client_cart.py`:

```python
import httpx
import pytest

from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError


def _client(handler):
    http = httpx.Client(base_url="https://api.kroger.com", transport=httpx.MockTransport(handler))
    return KrogerClient(http=http, client_id="c", client_secret="s", redirect_uri="u")


def test_add_to_cart_sends_put_with_items_array():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["json"] = request.read().decode()
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(204)

    _client(handler).add_to_cart("tok", upc="0001", quantity=2, modality="PICKUP")
    assert seen["method"] == "PUT"
    assert seen["path"] == "/v1/cart/add"
    assert seen["auth"] == "Bearer tok"
    assert '"upc": "0001"' in seen["json"] or '"upc":"0001"' in seen["json"]
    assert "PICKUP" in seen["json"]


def test_add_to_cart_invalid_upc_raises_kroger_error():
    def handler(request):
        return httpx.Response(400, json={"errors": {"reason": "Invalid.UPC"}})

    with pytest.raises(KrogerError):
        _client(handler).add_to_cart("tok", upc="bad", quantity=1, modality="PICKUP")


def test_add_to_cart_401_raises_auth_error():
    def handler(request):
        return httpx.Response(401, json={"error": "unauthorized"})

    with pytest.raises(KrogerAuthError):
        _client(handler).add_to_cart("tok", upc="0001", quantity=1, modality="PICKUP")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kroger_client_cart.py -v`
Expected: FAIL — `AttributeError: ... 'add_to_cart'`.

- [ ] **Step 3: Implement `add_to_cart`**

Add to `KrogerClient` in `backend/app/kroger/client.py`:

```python
    def add_to_cart(self, token: str, *, upc: str, quantity: int, modality: str) -> None:
        """PUT a single item to the customer's cart. Raises on any non-2xx. One item per
        call so callers get truthful per-item success/failure (cart is write-only)."""
        resp = self._http.put(
            "/v1/cart/add",
            json={"items": [{"upc": upc, "quantity": quantity, "modality": modality}]},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        self._raise_for_status(resp)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kroger_client_cart.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kroger/client.py tests/test_kroger_client_cart.py
git commit -m "feat(kroger): client add_to_cart (PUT /v1/cart/add, per-item)"
```

---

## Task 8: `kroger/auth.py` — token persistence + auto-refresh

**Files:**
- Create: `backend/app/kroger/auth.py`
- Test: `backend/tests/test_kroger_auth.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kroger_auth.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.kroger import auth
from app.kroger.client import KrogerAuthError
from app.kroger.schemas import TokenResp
from app.models import KrogerAuth


def _save(db, access="a", refresh="r", expires_in=1800, scope="product.compact"):
    return auth.save_tokens(db, TokenResp(access_token=access, refresh_token=refresh,
                                          expires_in=expires_in, scope=scope))


def test_save_tokens_creates_single_row(db_session):
    _save(db_session)
    _save(db_session, access="a2", refresh="r2")
    rows = db_session.query(KrogerAuth).all()
    assert len(rows) == 1
    assert rows[0].access_token == "a2"


def test_get_valid_token_returns_unexpired(db_session):
    _save(db_session, access="good")
    client = MagicMock()
    assert auth.get_valid_token(db_session, client) == "good"
    client.refresh.assert_not_called()


def test_get_valid_token_refreshes_when_expired(db_session):
    row = _save(db_session, access="old", refresh="r1")
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.flush()
    client = MagicMock()
    client.refresh.return_value = TokenResp(access_token="new", refresh_token="r2", expires_in=1800)
    assert auth.get_valid_token(db_session, client) == "new"
    client.refresh.assert_called_once_with("r1")


def test_get_valid_token_not_connected_raises(db_session):
    with pytest.raises(auth.NotConnectedError):
        auth.get_valid_token(db_session, MagicMock())


def test_get_valid_token_refresh_failure_propagates(db_session):
    row = _save(db_session, refresh="r1")
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.flush()
    client = MagicMock()
    client.refresh.side_effect = KrogerAuthError("bad refresh")
    with pytest.raises(KrogerAuthError):
        auth.get_valid_token(db_session, client)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kroger_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: app.kroger.auth`.

- [ ] **Step 3: Implement `auth.py`**

Create `backend/app/kroger/auth.py`:

```python
"""Owns the single kroger_auth row: persistence + valid-token retrieval with auto-refresh."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kroger.client import KrogerClient
from app.kroger.schemas import TokenResp
from app.models import KrogerAuth

# Refresh a little early so a token doesn't expire mid-request.
_EXPIRY_BUFFER = timedelta(seconds=60)


class NotConnectedError(Exception):
    """No Kroger tokens stored yet — the user must connect first."""


def get_auth(db: Session) -> KrogerAuth | None:
    return db.execute(select(KrogerAuth)).scalars().first()


def _expires_at(token: TokenResp) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=token.expires_in)


def save_tokens(db: Session, token: TokenResp) -> KrogerAuth:
    """Upsert the single tokens row. Keeps the existing refresh_token if a refresh
    response omits one."""
    row = get_auth(db)
    scopes = token.scope.split() if token.scope else []
    if row is None:
        row = KrogerAuth(
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
            expires_at=_expires_at(token),
            scopes=scopes,
        )
        db.add(row)
    else:
        row.access_token = token.access_token
        if token.refresh_token:
            row.refresh_token = token.refresh_token
        row.expires_at = _expires_at(token)
        if scopes:
            row.scopes = scopes
    db.flush()
    return row


def get_valid_token(db: Session, client: KrogerClient) -> str:
    """Return a non-expired customer access token, refreshing transparently.
    Raises NotConnectedError if never connected, KrogerAuthError if refresh fails."""
    row = get_auth(db)
    if row is None:
        raise NotConnectedError("Kroger account is not connected")
    if row.expires_at <= datetime.now(timezone.utc) + _EXPIRY_BUFFER:
        token = client.refresh(row.refresh_token)  # raises KrogerAuthError on failure
        row = save_tokens(db, token)
    return row.access_token
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kroger_auth.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add app/kroger/auth.py tests/test_kroger_auth.py
git commit -m "feat(kroger): token persistence + get_valid_token auto-refresh"
```

---

## Task 9: `kroger/router.py` — status, login, callback, locations

**Files:**
- Create: `backend/app/kroger/router.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_kroger_router.py`

The router builds a `KrogerClient` via a dependency so tests can override it. OAuth `state` is held in a module-level in-process set (single-user local app).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kroger_router.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.kroger.router import get_kroger_client
from app.kroger.schemas import Location, TokenResp
from app.main import app
from app.models import KrogerAuth


def _client(db_session, kroger):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_kroger_client] = lambda: kroger
    return TestClient(app)


def test_status_disconnected(db_session):
    client = _client(db_session, MagicMock())
    resp = client.get("/kroger/status")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "expired": False}
    app.dependency_overrides.clear()


def test_status_connected(db_session):
    db_session.add(KrogerAuth(access_token="a", refresh_token="r",
                              expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db_session.flush()
    client = _client(db_session, MagicMock())
    assert client.get("/kroger/status").json() == {"connected": True, "expired": False}
    app.dependency_overrides.clear()


def test_login_returns_authorize_url(db_session):
    kroger = MagicMock()
    kroger.authorize_url.return_value = "https://api.kroger.com/v1/connect/oauth2/authorize?x=1"
    client = _client(db_session, kroger)
    body = client.get("/kroger/login").json()
    assert body["url"].startswith("https://api.kroger.com")
    app.dependency_overrides.clear()


def test_callback_exchanges_code_and_saves(db_session):
    kroger = MagicMock()
    kroger.authorize_url.return_value = "https://x/?state=STATE123"
    kroger.exchange_code.return_value = TokenResp(access_token="a", refresh_token="r", expires_in=1800)
    client = _client(db_session, kroger)
    # First call /login to register the state the router generates; capture it.
    from app.kroger import router as kr
    kr._PENDING_STATES.add("STATE123")
    resp = client.get("/auth/callback", params={"code": "c", "state": "STATE123"},
                      follow_redirects=False)
    assert resp.status_code in (200, 307)
    assert db_session.query(KrogerAuth).count() == 1
    kroger.exchange_code.assert_called_once_with("c")
    app.dependency_overrides.clear()


def test_callback_bad_state_rejected(db_session):
    client = _client(db_session, MagicMock())
    resp = client.get("/auth/callback", params={"code": "c", "state": "nope"})
    assert resp.status_code == 400
    app.dependency_overrides.clear()


def test_locations_search(db_session):
    db_session.add(KrogerAuth(access_token="a", refresh_token="r",
                              expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db_session.flush()
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_locations.return_value = [Location(location_id="L1", name="Store", address="1 Main")]
    client = _client(db_session, kroger)
    body = client.get("/kroger/locations", params={"zip": "45202"}).json()
    assert body[0]["location_id"] == "L1"
    kroger.search_locations.assert_called_once_with("ct", "45202")
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kroger_router.py -v`
Expected: FAIL — `ModuleNotFoundError: app.kroger.router`.

- [ ] **Step 3: Implement the router**

Create `backend/app/kroger/router.py`:

```python
"""HTTP layer for Kroger account connection + store lookup. Thin; delegates to client/auth."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.kroger import auth
from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError
from app.kroger.schemas import KrogerStatus, Location, LoginUrl

router = APIRouter(tags=["kroger"])

# Single-user local app: pending OAuth state tokens held in-process for CSRF protection.
_PENDING_STATES: set[str] = set()


def get_kroger_client() -> KrogerClient:
    return KrogerClient()


@router.get("/kroger/status", response_model=KrogerStatus)
def status(db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    row = auth.get_auth(db)
    if row is None:
        return KrogerStatus(connected=False, expired=False)
    expired = row.expires_at <= datetime.now(timezone.utc)
    return KrogerStatus(connected=True, expired=expired)


@router.get("/kroger/login", response_model=LoginUrl)
def login(kroger: KrogerClient = Depends(get_kroger_client)):
    state = secrets.token_urlsafe(16)
    _PENDING_STATES.add(state)
    return LoginUrl(url=kroger.authorize_url(state))


@router.get("/auth/callback")
def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    if state not in _PENDING_STATES:
        raise HTTPException(status_code=400, detail="invalid or expired state")
    _PENDING_STATES.discard(state)
    try:
        token = kroger.exchange_code(code)
    except KrogerError as exc:
        raise HTTPException(status_code=502, detail=f"Kroger token exchange failed: {exc}")
    auth.save_tokens(db, token)
    db.commit()
    # Send the user back to the web app (functional; Phase 6 polishes this).
    return RedirectResponse(url=get_settings().cors_origins[0], status_code=307)


@router.get("/kroger/locations", response_model=list[Location])
def locations(
    zip: str = Query(..., min_length=3),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        token = kroger.fetch_client_token()
        return kroger.search_locations(token.access_token, zip)
    except KrogerAuthError as exc:
        raise HTTPException(status_code=502, detail=f"Kroger auth failed: {exc}")
    except KrogerError as exc:
        raise HTTPException(status_code=503, detail=f"Kroger unavailable: {exc}")
```

Register the router in `backend/app/main.py`. Add the import near the other router imports:

```python
from app.kroger.router import router as kroger_router
```

And after `app.include_router(list_router)`:

```python
app.include_router(kroger_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kroger_router.py -v`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add app/kroger/router.py app/main.py tests/test_kroger_router.py
git commit -m "feat(kroger): status/login/callback/locations endpoints"
```

---

## Task 10: `matching/schemas.py` — API models

**Files:**
- Create: `backend/app/matching/schemas.py`
- Test: `backend/tests/test_matching_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_matching_schemas.py`:

```python
from app.matching.schemas import (
    ConfirmRequest,
    MatchItemRead,
    MatchRead,
    ProductChoice,
    SendRequest,
    SendItemResult,
    SendResult,
)


def test_send_request_defaults_pickup():
    assert SendRequest().modality == "PICKUP"


def test_models_construct():
    choice = ProductChoice(upc="0001", description="Flour", size="5 lb", price=3.49, stock_level="HIGH")
    item = MatchItemRead(item_id=1, ingredient_id=2, ingredient_name="flour",
                         total_qty=3.0, total_unit="cup", purchase_qty=1,
                         purchase_qty_estimated=True, kroger_upc=None, current=None)
    read = MatchRead(connected=True, store_location_id="L1", items=[item])
    assert read.items[0].ingredient_name == "flour"
    assert choice.price == 3.49
    assert ConfirmRequest(kroger_upc="0001").kroger_description is None
    result = SendResult(status="sent_to_kroger", results=[SendItemResult(upc="0001", ok=True, error=None)])
    assert result.results[0].ok is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_matching_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: app.matching.schemas`.

- [ ] **Step 3: Create the schemas**

Create `backend/app/matching/schemas.py`:

```python
"""Pydantic request/response models for the matching + send API."""

from __future__ import annotations

from pydantic import BaseModel


class ProductChoice(BaseModel):
    upc: str
    description: str
    size: str | None = None
    price: float | None = None
    stock_level: str | None = None


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


class MatchRead(BaseModel):
    connected: bool
    store_location_id: str | None
    items: list[MatchItemRead]


class ConfirmRequest(BaseModel):
    kroger_upc: str
    kroger_description: str | None = None
    package_size: str | None = None


class SendRequest(BaseModel):
    modality: str = "PICKUP"


class SendItemResult(BaseModel):
    upc: str
    ok: bool
    error: str | None = None


class SendResult(BaseModel):
    status: str
    results: list[SendItemResult]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_matching_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/matching/schemas.py tests/test_matching_schemas.py
git commit -m "feat(matching): API schemas for match/confirm/send"
```

---

## Task 11: `matching/service.py` — match state, confirm, product search

**Files:**
- Create: `backend/app/matching/service.py`
- Test: `backend/tests/test_matching_service.py`

This task covers reading match state, confirming a product (persist map + item + recompute purchase_qty), and per-item product search. Sending is Task 12.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_matching_service.py`:

```python
from unittest.mock import MagicMock

import pytest

from app.kroger.schemas import Product, TokenResp
from app.matching import service
from app.matching.schemas import ConfirmRequest
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    IngredientProductMap,
)


def _draft_with_item(db, total_qty=3.0, total_unit="lb", store="L1"):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking",
                     default_purchase_unit="bag")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id=store)
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id,
                           total_qty=total_qty, total_unit=total_unit, pantry_status="needed")
    db.add(item)
    db.flush()
    return gl, ing, item


def test_get_match_state_reports_items_and_store(db_session):
    gl, ing, item = _draft_with_item(db_session)
    state = service.get_match_state(db_session)
    assert state.connected is False  # no kroger_auth row
    assert state.store_location_id == "L1"
    assert state.items[0].ingredient_name == "flour"
    assert state.items[0].kroger_upc is None


def test_get_match_state_skips_skipped_items(db_session):
    gl, ing, item = _draft_with_item(db_session)
    item.pantry_status = "skipped"
    db_session.flush()
    assert service.get_match_state(db_session).items == []


def test_confirm_product_persists_map_and_recomputes_qty(db_session):
    gl, ing, item = _draft_with_item(db_session, total_qty=3.0, total_unit="lb")
    service.confirm_product(
        db_session, item.id,
        ConfirmRequest(kroger_upc="0001", kroger_description="AP Flour", package_size="1 lb"),
    )
    db_session.flush()
    assert item.kroger_upc == "0001"
    assert item.purchase_qty == 3  # 3 lb / 1 lb
    assert item.purchase_qty_estimated is False
    mapping = db_session.query(IngredientProductMap).filter_by(ingredient_id=ing.id).one()
    assert mapping.kroger_upc == "0001"
    assert mapping.package_size == "1 lb"


def test_confirm_product_updates_existing_map_row(db_session):
    gl, ing, item = _draft_with_item(db_session)
    db_session.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="old",
                                        kroger_description="Old", package_size="2 lb"))
    db_session.flush()
    service.confirm_product(db_session, item.id,
                            ConfirmRequest(kroger_upc="new", package_size="1 lb"))
    db_session.flush()
    rows = db_session.query(IngredientProductMap).filter_by(ingredient_id=ing.id).all()
    assert len(rows) == 1
    assert rows[0].kroger_upc == "new"


def test_confirm_product_estimated_when_units_incompatible(db_session):
    gl, ing, item = _draft_with_item(db_session, total_qty=3.0, total_unit="cup")
    service.confirm_product(db_session, item.id,
                            ConfirmRequest(kroger_upc="0001", package_size="5 lb"))
    db_session.flush()
    assert item.purchase_qty == 1
    assert item.purchase_qty_estimated is True


def test_confirm_product_unknown_item_raises(db_session):
    with pytest.raises(service.ItemNotFoundError):
        service.confirm_product(db_session, 9999, ConfirmRequest(kroger_upc="x"))


def test_search_item_products_uses_store_and_canonical_name(db_session):
    gl, ing, item = _draft_with_item(db_session)
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = [
        Product(upc="0001", description="AP Flour", size="5 lb", price=3.49, stock_level="HIGH")
    ]
    choices = service.search_item_products(db_session, kroger, item.id, query=None)
    assert choices[0].upc == "0001"
    kroger.search_products.assert_called_once_with("ct", "flour", "L1")


def test_search_item_products_no_store_raises(db_session):
    gl, ing, item = _draft_with_item(db_session, store=None)
    with pytest.raises(service.NoStoreSelectedError):
        service.search_item_products(db_session, MagicMock(), item.id, query=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_matching_service.py -v`
Expected: FAIL — `ModuleNotFoundError: app.matching.service`.

- [ ] **Step 3: Implement the service (match/confirm/search)**

Create `backend/app/matching/service.py`:

```python
"""Matching + send orchestration. The only writer of ingredient_product_map for picks,
and of grocery_list_items.kroger_upc / purchase_qty / purchase_qty_estimated."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consolidate.service import get_or_create_draft
from app.kroger import auth as kroger_auth
from app.kroger.client import KrogerClient
from app.matching.purchase import compute_purchase_qty
from app.matching.schemas import (
    MatchItemRead,
    MatchRead,
    ProductChoice,
    ConfirmRequest,
)
from app.models import GroceryList, GroceryListItem, Ingredient, IngredientProductMap


class ItemNotFoundError(Exception):
    """The grocery_list_item id does not exist."""


class NoStoreSelectedError(Exception):
    """A store must be chosen on the draft before searching products."""


def _kept_items(db: Session, list_id: int) -> list[GroceryListItem]:
    rows = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == list_id)
    ).scalars().all()
    return [r for r in rows if r.pantry_status != "skipped"]


def _current_choice(db: Session, item: GroceryListItem) -> ProductChoice | None:
    if item.kroger_upc is None:
        return None
    mapping = db.execute(
        select(IngredientProductMap).where(IngredientProductMap.kroger_upc == item.kroger_upc)
    ).scalars().first()
    if mapping is None:
        return ProductChoice(upc=item.kroger_upc, description="")
    return ProductChoice(
        upc=mapping.kroger_upc,
        description=mapping.kroger_description or "",
        size=mapping.package_size,
    )


def get_match_state(db: Session) -> MatchRead:
    draft = get_or_create_draft(db)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    items = [
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
        )
        for it in _kept_items(db, draft.id)
    ]
    return MatchRead(
        connected=kroger_auth.get_auth(db) is not None,
        store_location_id=draft.store_location_id,
        items=items,
    )


def _get_item(db: Session, item_id: int) -> GroceryListItem:
    item = db.get(GroceryListItem, item_id)
    if item is None:
        raise ItemNotFoundError(f"grocery_list_item {item_id} not found")
    return item


def confirm_product(db: Session, item_id: int, req: ConfirmRequest) -> None:
    item = _get_item(db, item_id)

    mapping = db.execute(
        select(IngredientProductMap).where(
            IngredientProductMap.ingredient_id == item.ingredient_id
        )
    ).scalars().first()
    if mapping is None:
        mapping = IngredientProductMap(ingredient_id=item.ingredient_id)
        db.add(mapping)
    mapping.kroger_upc = req.kroger_upc
    mapping.kroger_description = req.kroger_description
    mapping.package_size = req.package_size
    mapping.is_default = True

    item.kroger_upc = req.kroger_upc
    qty, estimated = compute_purchase_qty(item.total_qty, item.total_unit, req.package_size)
    item.purchase_qty = qty
    item.purchase_qty_estimated = estimated
    db.flush()


def search_item_products(
    db: Session, client: KrogerClient, item_id: int, query: str | None
) -> list[ProductChoice]:
    item = _get_item(db, item_id)
    gl = db.get(GroceryList, item.list_id)
    if gl is None or gl.store_location_id is None:
        raise NoStoreSelectedError("pick a store before searching products")

    ingredient = db.get(Ingredient, item.ingredient_id)
    term = query or (ingredient.canonical_name if ingredient else "")
    token = client.fetch_client_token()
    products = client.search_products(token.access_token, term, gl.store_location_id)
    return [
        ProductChoice(
            upc=p.upc, description=p.description, size=p.size,
            price=p.price, stock_level=p.stock_level,
        )
        for p in products
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_matching_service.py -v`
Expected: PASS (all 8).

- [ ] **Step 5: Commit**

```bash
git add app/matching/service.py tests/test_matching_service.py
git commit -m "feat(matching): match state, confirm-and-persist, product search"
```

---

## Task 12: `matching/service.py` — send_to_cart

**Files:**
- Modify: `backend/app/matching/service.py` (add `send_to_cart`)
- Test: `backend/tests/test_matching_send.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_matching_send.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.kroger.client import KrogerAuthError, KrogerError
from app.matching import service
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    KrogerAuth,
    PurchaseLog,
)


def _connected(db):
    db.add(KrogerAuth(access_token="a", refresh_token="r",
                      expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db.flush()


def _draft_with_items(db, upcs):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id="L1")
    db.add(gl)
    db.flush()
    items = []
    for upc in upcs:
        it = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=3.0,
                             total_unit="lb", purchase_qty=2, kroger_upc=upc,
                             pantry_status="needed")
        db.add(it)
        items.append(it)
    db.flush()
    return gl, ing, items


def test_send_pushes_each_item_and_logs_success(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["0001", "0002"])
    kroger = MagicMock()
    result = service.send_to_cart(db_session, kroger, modality="PICKUP")
    db_session.flush()
    assert all(r.ok for r in result.results)
    assert kroger.add_to_cart.call_count == 2
    assert gl.status == "sent_to_kroger"
    assert gl.sent_at is not None
    assert db_session.query(PurchaseLog).count() == 2


def test_send_skips_items_without_upc(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["0001"])
    db_session.add(GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=1.0,
                                   total_unit="lb", purchase_qty=1, kroger_upc=None,
                                   pantry_status="needed"))
    db_session.flush()
    kroger = MagicMock()
    result = service.send_to_cart(db_session, kroger, modality="PICKUP")
    assert len(result.results) == 1
    assert kroger.add_to_cart.call_count == 1


def test_send_partial_failure_logs_only_successes(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["good", "bad"])
    kroger = MagicMock()

    def add(token, *, upc, quantity, modality):
        if upc == "bad":
            raise KrogerError("Invalid.UPC")

    kroger.add_to_cart.side_effect = add
    result = service.send_to_cart(db_session, kroger, modality="PICKUP")
    db_session.flush()
    by_upc = {r.upc: r for r in result.results}
    assert by_upc["good"].ok is True
    assert by_upc["bad"].ok is False and by_upc["bad"].error
    assert db_session.query(PurchaseLog).count() == 1
    assert gl.status == "sent_to_kroger"  # at least one succeeded


def test_send_auth_failure_aborts_with_error(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["0001"])
    kroger = MagicMock()
    kroger.add_to_cart.side_effect = KrogerAuthError("token revoked")
    with pytest.raises(KrogerAuthError):
        service.send_to_cart(db_session, kroger, modality="PICKUP")


def test_send_not_connected_raises(db_session):
    gl, ing, items = _draft_with_items(db_session, ["0001"])
    with pytest.raises(service.kroger_auth.NotConnectedError):
        service.send_to_cart(db_session, MagicMock(), modality="PICKUP")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_matching_send.py -v`
Expected: FAIL — `AttributeError: module 'app.matching.service' has no attribute 'send_to_cart'`.

- [ ] **Step 3: Implement `send_to_cart`**

Add to `backend/app/matching/service.py`. Add these imports at the top (next to existing imports):

```python
from datetime import datetime, timezone

from app.kroger.client import KrogerAuthError, KrogerError
from app.matching.schemas import SendItemResult, SendResult
from app.models import PurchaseLog
```

(`GroceryList` is already imported at the top of `service.py` from Task 11; `datetime`/`timezone` may need adding if not already present.)

Append this function:

```python
def send_to_cart(db: Session, client: KrogerClient, modality: str = "PICKUP") -> SendResult:
    """Push each item with a UPC to the cart, one PUT per item. Logs only successes to
    purchase_log. Raises NotConnectedError/KrogerAuthError if the token is unusable."""
    draft = get_or_create_draft(db)
    token = kroger_auth.get_valid_token(db, client)  # NotConnected/Auth errors propagate

    results: list[SendItemResult] = []
    any_success = False
    for item in _kept_items(db, draft.id):
        if item.kroger_upc is None:
            continue
        try:
            client.add_to_cart(
                token, upc=item.kroger_upc, quantity=item.purchase_qty, modality=modality
            )
        except KrogerAuthError:
            raise  # token died mid-send: abort so the user re-auths, no partial lie
        except KrogerError as exc:
            results.append(SendItemResult(upc=item.kroger_upc, ok=False, error=str(exc)))
            continue
        any_success = True
        db.add(
            PurchaseLog(
                ingredient_id=item.ingredient_id,
                kroger_upc=item.kroger_upc,
                qty=item.total_qty,
                unit=item.total_unit,
                source_list_id=draft.id,
            )
        )
        results.append(SendItemResult(upc=item.kroger_upc, ok=True, error=None))

    if any_success:
        draft.status = "sent_to_kroger"
        draft.sent_at = datetime.now(timezone.utc)
    db.flush()
    return SendResult(status=draft.status, results=results)
```

Also expose the auth module under the name the test references — confirm the top of `service.py` imports it as `from app.kroger import auth as kroger_auth` (it already does from Task 11). The test refers to `service.kroger_auth.NotConnectedError`, which resolves through that import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_matching_send.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add app/matching/service.py tests/test_matching_send.py
git commit -m "feat(matching): send_to_cart tolerant per-item push + purchase_log"
```

---

## Task 13: `matching/router.py` — match, search, confirm, send

**Files:**
- Create: `backend/app/matching/router.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_matching_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_matching_router.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.kroger.schemas import Product, TokenResp
from app.kroger.router import get_kroger_client
from app.main import app
from app.models import GroceryList, GroceryListItem, Ingredient, KrogerAuth


def _seed(db, store="L1", upc=None):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id=store)
    db.add(gl)
    db.flush()
    it = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=3.0,
                         total_unit="lb", purchase_qty=1, kroger_upc=upc, pantry_status="needed")
    db.add(it)
    db.flush()
    return gl, ing, it


def _client(db, kroger=None):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_kroger_client] = lambda: kroger or MagicMock()
    return TestClient(app)


def test_get_match(db_session):
    _seed(db_session)
    client = _client(db_session)
    body = client.get("/list/match").json()
    assert body["store_location_id"] == "L1"
    assert body["items"][0]["ingredient_name"] == "flour"
    app.dependency_overrides.clear()


def test_search_products_endpoint(db_session):
    gl, ing, it = _seed(db_session)
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = [Product(upc="0001", description="Flour", size="5 lb")]
    client = _client(db_session, kroger)
    body = client.get(f"/list/items/{it.id}/products", params={"q": "flour"}).json()
    assert body[0]["upc"] == "0001"
    app.dependency_overrides.clear()


def test_confirm_product_endpoint(db_session):
    gl, ing, it = _seed(db_session)
    client = _client(db_session)
    resp = client.post(f"/list/items/{it.id}/product",
                       json={"kroger_upc": "0001", "package_size": "1 lb"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["kroger_upc"] == "0001"
    app.dependency_overrides.clear()


def test_send_endpoint_requires_connection(db_session):
    _seed(db_session, upc="0001")
    client = _client(db_session)
    resp = client.post("/list/send", json={"modality": "PICKUP"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "reauth_required"
    app.dependency_overrides.clear()


def test_send_endpoint_success(db_session):
    gl, ing, it = _seed(db_session, upc="0001")
    db_session.add(KrogerAuth(access_token="a", refresh_token="r",
                              expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db_session.flush()
    kroger = MagicMock()
    client = _client(db_session, kroger)
    resp = client.post("/list/send", json={"modality": "PICKUP"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent_to_kroger"
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_matching_router.py -v`
Expected: FAIL — `ModuleNotFoundError: app.matching.router`.

- [ ] **Step 3: Implement the router**

Create `backend/app/matching/router.py`:

```python
"""HTTP layer for product matching + cart send. Thin; delegates to matching.service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.kroger.auth import NotConnectedError
from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError
from app.kroger.router import get_kroger_client
from app.matching import service
from app.matching.schemas import (
    ConfirmRequest,
    MatchRead,
    ProductChoice,
    SendRequest,
    SendResult,
)

router = APIRouter(prefix="/list", tags=["matching"])


@router.get("/match", response_model=MatchRead)
def get_match(db: Session = Depends(get_db)):
    state = service.get_match_state(db)
    db.commit()
    return state


@router.get("/items/{item_id}/products", response_model=list[ProductChoice])
def search_products(
    item_id: int,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        return service.search_item_products(db, kroger, item_id, query=q)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.NoStoreSelectedError as exc:
        raise HTTPException(status_code=409, detail={"error": "no_store", "message": str(exc)})
    except KrogerError as exc:
        raise HTTPException(status_code=503, detail=f"Kroger unavailable: {exc}")


@router.post("/items/{item_id}/product", response_model=MatchRead)
def confirm_product(item_id: int, body: ConfirmRequest, db: Session = Depends(get_db)):
    try:
        service.confirm_product(db, item_id, body)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    state = service.get_match_state(db)
    db.commit()
    return state


@router.post("/send", response_model=SendResult)
def send(
    body: SendRequest,
    db: Session = Depends(get_db),
    kroger: KrogerClient = Depends(get_kroger_client),
):
    try:
        result = service.send_to_cart(db, kroger, modality=body.modality)
    except (NotConnectedError, KrogerAuthError) as exc:
        raise HTTPException(
            status_code=409, detail={"error": "reauth_required", "message": str(exc)}
        )
    db.commit()
    return result
```

Register in `backend/app/main.py`. Add near the other imports:

```python
from app.matching.router import router as matching_router
```

And after `app.include_router(kroger_router)`:

```python
app.include_router(matching_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_matching_router.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all tests pass (existing 82 + the new Phase 4 tests).

- [ ] **Step 6: Commit**

```bash
git add app/matching/router.py app/main.py tests/test_matching_router.py
git commit -m "feat(matching): match/search/confirm/send endpoints"
```

---

## Task 14: Frontend — API client + types

**Files:**
- Modify: `frontend/src/recipes/types.ts` (append)
- Modify: `frontend/src/api.ts` (append)
- Test: `frontend/src/recipes/krogerApi.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/recipes/krogerApi.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import { confirmProduct, getKrogerStatus, getMatch, searchItemProducts, sendCart } from "../api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown, ok = true) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok,
    status: ok ? 200 : 409,
    json: async () => body,
  } as Response);
}

describe("kroger api", () => {
  it("getKrogerStatus calls /kroger/status", async () => {
    const f = mockFetch({ connected: true, expired: false });
    const res = await getKrogerStatus();
    expect(res.connected).toBe(true);
    expect(f.mock.calls[0][0]).toContain("/kroger/status");
  });

  it("getMatch calls /list/match", async () => {
    const f = mockFetch({ connected: true, store_location_id: "L1", items: [] });
    await getMatch();
    expect(f.mock.calls[0][0]).toContain("/list/match");
  });

  it("searchItemProducts hits the per-item products endpoint", async () => {
    const f = mockFetch([{ upc: "0001", description: "Flour" }]);
    const res = await searchItemProducts(5, "flour");
    expect(res[0].upc).toBe("0001");
    expect(f.mock.calls[0][0]).toContain("/list/items/5/products?q=flour");
  });

  it("confirmProduct POSTs the chosen product", async () => {
    const f = mockFetch({ connected: true, store_location_id: "L1", items: [] });
    await confirmProduct(5, { kroger_upc: "0001", package_size: "1 lb" });
    expect(f.mock.calls[0][1]?.method).toBe("POST");
  });

  it("sendCart POSTs modality", async () => {
    const f = mockFetch({ status: "sent_to_kroger", results: [] });
    await sendCart("PICKUP");
    const body = JSON.parse((f.mock.calls[0][1]?.body as string) ?? "{}");
    expect(body.modality).toBe("PICKUP");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- krogerApi`
Expected: FAIL — imports `getKrogerStatus`, `getMatch`, etc. do not exist.

- [ ] **Step 3: Add the types**

Append to `frontend/src/recipes/types.ts`:

```ts
export interface KrogerStatus {
  connected: boolean;
  expired: boolean;
}

export interface KrogerLocation {
  location_id: string;
  name: string;
  address: string;
}

export interface ProductChoice {
  upc: string;
  description: string;
  size: string | null;
  price: number | null;
  stock_level: string | null;
}

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
}

export interface MatchData {
  connected: boolean;
  store_location_id: string | null;
  items: MatchItem[];
}

export interface ConfirmProductBody {
  kroger_upc: string;
  kroger_description?: string | null;
  package_size?: string | null;
}

export interface SendItemResult {
  upc: string;
  ok: boolean;
  error: string | null;
}

export interface SendResult {
  status: string;
  results: SendItemResult[];
}
```

- [ ] **Step 4: Add the API functions**

Append to `frontend/src/api.ts` (extend the import line at the top to include the new types):

```ts
import type {
  ConfirmProductBody,
  KrogerLocation,
  KrogerStatus,
  MatchData,
  ProductChoice,
  SendResult,
} from "./recipes/types";

export async function getKrogerStatus(): Promise<KrogerStatus> {
  return json<KrogerStatus>(await fetch(`${BASE_URL}/kroger/status`));
}

export async function getKrogerLoginUrl(): Promise<{ url: string }> {
  return json<{ url: string }>(await fetch(`${BASE_URL}/kroger/login`));
}

export async function searchLocations(zip: string): Promise<KrogerLocation[]> {
  return json<KrogerLocation[]>(
    await fetch(`${BASE_URL}/kroger/locations?zip=${encodeURIComponent(zip)}`),
  );
}

export async function getMatch(): Promise<MatchData> {
  return json<MatchData>(await fetch(`${BASE_URL}/list/match`));
}

export async function searchItemProducts(
  itemId: number,
  q: string,
): Promise<ProductChoice[]> {
  return json<ProductChoice[]>(
    await fetch(`${BASE_URL}/list/items/${itemId}/products?q=${encodeURIComponent(q)}`),
  );
}

export async function confirmProduct(
  itemId: number,
  body: ConfirmProductBody,
): Promise<MatchData> {
  const res = await fetch(`${BASE_URL}/list/items/${itemId}/product`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<MatchData>(res);
}

export async function sendCart(modality: string): Promise<SendResult> {
  const res = await fetch(`${BASE_URL}/list/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modality }),
  });
  return json<SendResult>(res);
}
```

(If `import type { ... } from "./recipes/types"` already exists at the top of `api.ts`, merge the new names into that statement instead of adding a second import.)

- [ ] **Step 5: Run test to verify it passes**

Run (from `frontend/`): `npm test -- krogerApi`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.ts frontend/src/recipes/types.ts frontend/src/recipes/krogerApi.test.ts
git commit -m "feat(web): kroger/matching api client + types"
```

---

## Task 15: Frontend — Kroger connect + store picker screen

**Files:**
- Create: `frontend/src/recipes/KrogerSetup.tsx`
- Test: `frontend/src/recipes/KrogerSetup.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/recipes/KrogerSetup.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { KrogerSetup } from "./KrogerSetup";

afterEach(() => vi.restoreAllMocks());

describe("KrogerSetup", () => {
  it("shows disconnected state and a connect button", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: false, expired: false });
    render(<KrogerSetup />);
    expect(await screen.findByRole("button", { name: /connect kroger/i })).toBeInTheDocument();
  });

  it("searches stores by zip and lists them", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: false });
    const search = vi.spyOn(api, "searchLocations").mockResolvedValue([
      { location_id: "L1", name: "Kroger Downtown", address: "1 Main St" },
    ]);
    render(<KrogerSetup />);
    fireEvent.change(await screen.findByLabelText(/zip/i), { target: { value: "45202" } });
    fireEvent.click(screen.getByRole("button", { name: /find stores/i }));
    await waitFor(() => expect(search).toHaveBeenCalledWith("45202"));
    expect(await screen.findByText(/Kroger Downtown/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- KrogerSetup`
Expected: FAIL — module `./KrogerSetup` not found.

- [ ] **Step 3: Implement the screen**

Create `frontend/src/recipes/KrogerSetup.tsx`:

```tsx
import { useEffect, useState } from "react";

import { getKrogerLoginUrl, getKrogerStatus, searchLocations } from "../api";
import type { KrogerLocation, KrogerStatus } from "./types";

export function KrogerSetup() {
  const [status, setStatus] = useState<KrogerStatus | null>(null);
  const [zip, setZip] = useState("");
  const [stores, setStores] = useState<KrogerLocation[]>([]);

  useEffect(() => {
    getKrogerStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  async function connect() {
    const { url } = await getKrogerLoginUrl();
    window.location.href = url;
  }

  async function findStores() {
    setStores(await searchLocations(zip));
  }

  return (
    <section>
      <h2>Kroger</h2>
      {status?.connected ? (
        <p>Connected{status.expired ? " (session expired — reconnect)" : ""}.</p>
      ) : (
        <button onClick={connect}>Connect Kroger</button>
      )}

      <h3>Home store</h3>
      <label>
        Zip code
        <input value={zip} onChange={(e) => setZip(e.target.value)} />
      </label>
      <button onClick={findStores}>Find stores</button>
      <ul>
        {stores.map((s) => (
          <li key={s.location_id}>
            {s.name} — {s.address}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npm test -- KrogerSetup`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/KrogerSetup.tsx frontend/src/recipes/KrogerSetup.test.tsx
git commit -m "feat(web): Kroger connect + store picker screen"
```

---

## Task 16: Frontend — match/review + send screen

**Files:**
- Create: `frontend/src/recipes/MatchReview.tsx`
- Test: `frontend/src/recipes/MatchReview.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/recipes/MatchReview.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { MatchReview } from "./MatchReview";

const baseMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    {
      item_id: 1,
      ingredient_id: 2,
      ingredient_name: "flour",
      total_qty: 3,
      total_unit: "lb",
      purchase_qty: 1,
      purchase_qty_estimated: true,
      kroger_upc: null,
      current: null,
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

describe("MatchReview", () => {
  it("lists items and flags estimated quantities", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    render(<MatchReview />);
    expect(await screen.findByText(/flour/)).toBeInTheDocument();
    expect(screen.getByText(/check quantity/i)).toBeInTheDocument();
  });

  it("searches products for an item", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const search = vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" },
    ]);
    render(<MatchReview />);
    fireEvent.click(await screen.findByRole("button", { name: /find product/i }));
    await waitFor(() => expect(search).toHaveBeenCalledWith(1, "flour"));
    expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
  });

  it("sends the cart and shows the result", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const send = vi.spyOn(api, "sendCart").mockResolvedValue({
      status: "sent_to_kroger",
      results: [{ upc: "0001", ok: true, error: null }],
    });
    render(<MatchReview />);
    fireEvent.click(await screen.findByRole("button", { name: /send to kroger cart/i }));
    await waitFor(() => expect(send).toHaveBeenCalledWith("PICKUP"));
    expect(await screen.findByText(/sent_to_kroger/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- MatchReview`
Expected: FAIL — module `./MatchReview` not found.

- [ ] **Step 3: Implement the screen**

Create `frontend/src/recipes/MatchReview.tsx`:

```tsx
import { useEffect, useState } from "react";

import { confirmProduct, getMatch, searchItemProducts, sendCart } from "../api";
import type { MatchData, ProductChoice, SendResult } from "./types";

export function MatchReview() {
  const [match, setMatch] = useState<MatchData | null>(null);
  const [choices, setChoices] = useState<Record<number, ProductChoice[]>>({});
  const [modality, setModality] = useState("PICKUP");
  const [sendResult, setSendResult] = useState<SendResult | null>(null);

  useEffect(() => {
    getMatch().then(setMatch).catch(() => setMatch(null));
  }, []);

  async function find(itemId: number, name: string | null) {
    const results = await searchItemProducts(itemId, name ?? "");
    setChoices((c) => ({ ...c, [itemId]: results }));
  }

  async function pick(itemId: number, p: ProductChoice) {
    setMatch(
      await confirmProduct(itemId, {
        kroger_upc: p.upc,
        kroger_description: p.description,
        package_size: p.size,
      }),
    );
  }

  async function send() {
    setSendResult(await sendCart(modality));
    setMatch(await getMatch());
  }

  if (!match) return <p>Loading…</p>;

  return (
    <section>
      <h2>Match &amp; send</h2>
      {!match.connected && <p>Connect your Kroger account first.</p>}
      {!match.store_location_id && <p>Pick a home store first.</p>}

      <ul>
        {match.items.map((it) => (
          <li key={it.item_id}>
            <strong>{it.ingredient_name}</strong> — need{" "}
            {it.total_qty ?? "?"} {it.total_unit ?? ""}; buy {it.purchase_qty}{" "}
            {it.purchase_qty_estimated && <em>(check quantity)</em>}
            <div>
              {it.current ? (
                <span>Product: {it.current.description}</span>
              ) : (
                <span>No product chosen</span>
              )}
              <button onClick={() => find(it.item_id, it.ingredient_name)}>Find product</button>
            </div>
            <ul>
              {(choices[it.item_id] ?? []).map((p) => (
                <li key={p.upc}>
                  {p.description} {p.size ? `(${p.size})` : ""}{" "}
                  {p.price != null ? `$${p.price.toFixed(2)}` : ""}{" "}
                  {p.stock_level === "TEMPORARILY_OUT_OF_STOCK" && <em>out of stock</em>}
                  <button onClick={() => pick(it.item_id, p)}>Choose</button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      <label>
        Modality
        <select value={modality} onChange={(e) => setModality(e.target.value)}>
          <option value="PICKUP">Pickup</option>
          <option value="DELIVERY">Delivery</option>
        </select>
      </label>
      <button onClick={send}>Send to Kroger cart</button>

      {sendResult && (
        <div>
          <p>Status: {sendResult.status}</p>
          <ul>
            {sendResult.results.map((r) => (
              <li key={r.upc}>
                {r.upc}: {r.ok ? "added" : `failed — ${r.error}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npm test -- MatchReview`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/MatchReview.tsx frontend/src/recipes/MatchReview.test.tsx
git commit -m "feat(web): match/review + send-to-cart screen"
```

---

## Task 17: Frontend — wire screens into App nav

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx` (extend)

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/App.test.tsx` (inside the existing top-level `describe`, or as new tests — match the file's existing style):

```tsx
it("navigates to the Kroger setup screen", async () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: /^kroger$/i }));
  expect(await screen.findByRole("heading", { name: /^kroger$/i })).toBeInTheDocument();
});

it("navigates to the Match & send screen", async () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: /match & send/i }));
  expect(await screen.findByRole("heading", { name: /match & send/i })).toBeInTheDocument();
});
```

Ensure the test file imports `fireEvent` and `screen` from `@testing-library/react` (add to the existing import if missing).

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- App`
Expected: FAIL — no "Kroger" / "Match & send" nav buttons.

- [ ] **Step 3: Wire the screens in**

Modify `frontend/src/App.tsx`:

```tsx
import { useState } from "react";

import { AddRecipe } from "./recipes/AddRecipe";
import { GroceryList } from "./recipes/GroceryList";
import { KrogerSetup } from "./recipes/KrogerSetup";
import { MatchReview } from "./recipes/MatchReview";
import { RecipeDetail } from "./recipes/RecipeDetail";
import { RecipeList } from "./recipes/RecipeList";

type View =
  | { name: "list" }
  | { name: "add" }
  | { name: "grocery" }
  | { name: "kroger" }
  | { name: "match" }
  | { name: "detail"; id: number };

export function App() {
  const [view, setView] = useState<View>({ name: "list" });

  return (
    <main>
      <h1>Bushel</h1>
      <nav>
        <button onClick={() => setView({ name: "list" })}>Recipes</button>
        <button onClick={() => setView({ name: "add" })}>Add recipe</button>
        <button onClick={() => setView({ name: "grocery" })}>Grocery List</button>
        <button onClick={() => setView({ name: "kroger" })}>Kroger</button>
        <button onClick={() => setView({ name: "match" })}>Match &amp; send</button>
      </nav>

      {view.name === "list" && (
        <RecipeList onOpen={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "add" && (
        <AddRecipe onCreated={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "grocery" && <GroceryList />}
      {view.name === "kroger" && <KrogerSetup />}
      {view.name === "match" && <MatchReview />}
      {view.name === "detail" && <RecipeDetail recipeId={view.id} />}
    </main>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `frontend/`): `npm test -- App`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite**

Run (from `frontend/`): `npm test`
Expected: all component/api tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(web): add Kroger + Match&send to nav"
```

---

## Task 18: Manual live smoke test + docs

No automated code — this verifies the real Kroger integration end to end. Do this once after Tasks 1–17 are green.

**Files:**
- Modify: `README.md` (add a short "Kroger setup" section)

- [ ] **Step 1: Configure real credentials**

In `backend/.env`, set `kroger_client_id` and `kroger_client_secret` from your Kroger developer app. Confirm the app's registered redirect URI matches `kroger_redirect_uri` (default `http://localhost:8000/auth/callback`). Scopes enabled on the app: `product.compact`, `cart.basic:write`, `profile.compact`.

- [ ] **Step 2: Run the stack**

```bash
docker stop bushel-pg   # avoid the 5432 conflict
docker compose up
```

- [ ] **Step 3: Walk the flow in the browser**

1. Open the web app → **Kroger** tab → **Connect Kroger** → authorize on Kroger → land back in the app. Confirm `GET /kroger/status` shows connected (a `kroger_auth` row exists).
2. Enter your zip → **Find stores** → confirm stores list. (The store is set on the draft via the Grocery List flow / `PATCH /list`.)
3. Build a draft list (Recipes → add to list) with at least one item.
4. **Match & send** tab → **Find product** for an item → confirm products with price/stock appear → **Choose** one. Confirm the item shows the chosen product and a sane `purchase_qty`.
5. **Send to Kroger cart** (PICKUP) → confirm the per-item result shows "added", the list shows `sent_to_kroger`, and a `purchase_log` row was written.
6. Open the Kroger app/site and confirm the item is really in your cart.

- [ ] **Step 4: Document it**

Add a short "Kroger setup" subsection to `README.md` capturing Steps 1–3 above (env vars, redirect URI, the `docker stop bushel-pg` note) so the smoke test is repeatable.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: Kroger setup + Phase 4 smoke-test checklist"
```

---

## Done criteria

- `uv run pytest -q` (backend) and `npm test` (frontend) both green.
- Manual smoke test (Task 18) confirms a real item reaches the Kroger cart and a `purchase_log` row is written.
- Phase 4 merged to `master` via the finishing-a-development-branch skill.

## Phase 5 hand-off notes

- `ingredient_product_map` is now populated on confirm — Phase 5 adds **silent auto-reuse** (skip the confirm step when a default mapping exists) and the **pantry "still have it?"** prompts driven by `purchase_log`.
- `get_match_state` currently never auto-fills `kroger_upc` from the map; Phase 5 can pre-select the mapped product and surface stock at match time.

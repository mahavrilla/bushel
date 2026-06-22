# Phase 5: Matching & Pantry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-resolve each grocery item's Kroger product from the remembered map (changeable per item), and flag recently-bought items as "still have it?" with persistent keep/skip decisions.

**Architecture:** Add `matching.apply_remembered_products` (re-derives `kroger_upc`/`purchase_qty` from `ingredient_product_map` for unresolved items; called in `get_match_state`/`send_to_cart`). Add a new `app/pantry/` module (evaluate recent purchases → `maybe_have`; keep/skip decisions). `consolidate._recompute` snapshots/restores pantry decisions across list rebuilds. One new column `grocery_list_items.pantry_resolved`. Frontend adds a pantry-prompt panel + a "Change product" affordance. **No new Kroger/LLM calls — all DB logic.**

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + Pydantic (backend); React/TS + Vite + Tailwind + react-router (frontend); pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-06-21-bushel-phase-5-matching-pantry-design.md`

**Conventions:**
- Backend from `backend/`, `uv run`. **Tests MUST use the isolated test DB:** `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test` before `uv run pytest`/`alembic`. **NEVER port 5432** (the live dev DB; the conftest fixture drops all tables).
- Services flush (`db.flush()`); routers commit (`db.commit()`). Pantry/matching are DB-only — no Kroger client, no LLM.
- Frontend from `frontend/`: `npm test -- <pattern>`, `npm run build`. Uses the Phase 6 Warm Pantry primitives in `src/components/ui/`.
- Current Alembic head: `c1a2b3c4d5e6`.

---

## Task 1: Migration — `pantry_resolved` column + config

**Files:**
- Modify: `backend/app/models.py` (GroceryListItem)
- Modify: `backend/app/config.py`
- Create: `backend/migrations/versions/d4e5f6a7b8c9_add_pantry_resolved.py`
- Test: `backend/tests/test_models.py` (append)

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_models.py`:
```python
def test_grocery_list_item_pantry_resolved_defaults_false(db_session):
    from app.models import GroceryList, GroceryListItem, Ingredient

    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    gl = GroceryList(name="Draft", status="draft")
    db_session.add(gl)
    db_session.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id)
    db_session.add(item)
    db_session.flush()
    assert item.pantry_resolved is False
```

- [ ] **Step 2: Run it, confirm FAIL**

`export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_models.py::test_grocery_list_item_pantry_resolved_defaults_false -v`
Expected: FAIL — no `pantry_resolved` attribute.

- [ ] **Step 3: Add the column** — in `backend/app/models.py`, inside `class GroceryListItem`, after the `pantry_status` line add:
```python
    pantry_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```
(`Boolean` is already imported.)

- [ ] **Step 4: Add the config setting** — in `backend/app/config.py`, after the `anthropic_api_key` line inside `Settings`:
```python

    # Pantry "still have it?" — flag ingredients bought within this many days.
    pantry_recent_days: int = 14
```

- [ ] **Step 5: Create the migration** `backend/migrations/versions/d4e5f6a7b8c9_add_pantry_resolved.py`:
```python
"""add pantry_resolved to grocery_list_items

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3c4d5e6
Create Date: 2026-06-21 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'grocery_list_items',
        sa.Column('pantry_resolved', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('grocery_list_items', 'pantry_resolved')
```

- [ ] **Step 6: Apply + run the test**
```bash
export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test
uv run alembic upgrade head
uv run pytest tests/test_models.py::test_grocery_list_item_pantry_resolved_defaults_false -v
```
Expected: migration applies (`uv run alembic heads` shows `d4e5f6a7b8c9`); test PASSES.

- [ ] **Step 7: Commit**
```bash
git add app/models.py app/config.py migrations/versions/d4e5f6a7b8c9_add_pantry_resolved.py tests/test_models.py
git commit -m "feat(db): add grocery_list_items.pantry_resolved + pantry_recent_days config"
```

---

## Task 2: `matching.apply_remembered_products`

**Files:**
- Modify: `backend/app/matching/service.py`
- Test: `backend/tests/test_matching_apply.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_matching_apply.py`:
```python
from app.matching import service
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    IngredientProductMap,
)


def _draft_item(db, *, kroger_upc=None, total_qty=3.0, total_unit="lb", with_map=True):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id="L1")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=total_qty,
                           total_unit=total_unit, kroger_upc=kroger_upc, pantry_status="needed")
    db.add(item)
    if with_map:
        db.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="0001",
                                    kroger_description="AP Flour", package_size="1 lb"))
    db.flush()
    return gl, ing, item


def test_apply_resolves_unmapped_item_from_map(db_session):
    gl, ing, item = _draft_item(db_session, total_qty=3.0, total_unit="lb")
    service.apply_remembered_products(db_session)
    db_session.flush()
    assert item.kroger_upc == "0001"
    assert item.purchase_qty == 3  # 3 lb / 1 lb package
    assert item.purchase_qty_estimated is False


def test_apply_skips_items_already_resolved(db_session):
    gl, ing, item = _draft_item(db_session, kroger_upc="EXISTING")
    service.apply_remembered_products(db_session)
    assert item.kroger_upc == "EXISTING"


def test_apply_skips_items_with_no_mapping(db_session):
    gl, ing, item = _draft_item(db_session, with_map=False)
    service.apply_remembered_products(db_session)
    assert item.kroger_upc is None


def test_apply_is_idempotent(db_session):
    gl, ing, item = _draft_item(db_session)
    service.apply_remembered_products(db_session)
    service.apply_remembered_products(db_session)
    assert item.kroger_upc == "0001"


def test_get_match_state_auto_resolves(db_session):
    gl, ing, item = _draft_item(db_session)
    state = service.get_match_state(db_session)
    matched = next(i for i in state.items if i.item_id == item.id)
    assert matched.kroger_upc == "0001"
    assert matched.current is not None and matched.current.upc == "0001"
```

- [ ] **Step 2: Run, confirm FAIL**

`export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_matching_apply.py -v`
Expected: FAIL — `apply_remembered_products` doesn't exist.

- [ ] **Step 3: Implement** — in `backend/app/matching/service.py`, add this function (after `_current_choice`, before `get_match_state`):
```python
def apply_remembered_products(db: Session) -> None:
    """Re-derive kroger_upc + purchase_qty from the remembered ingredient_product_map for
    unresolved kept items. Idempotent; this is how confirmed picks survive list rebuilds."""
    draft = get_or_create_draft(db)
    maps = {
        m.ingredient_id: m
        for m in db.execute(select(IngredientProductMap)).scalars().all()
    }
    for item in _kept_items(db, draft.id):
        if item.kroger_upc is not None:
            continue
        mapping = maps.get(item.ingredient_id)
        if mapping is None:
            continue
        item.kroger_upc = mapping.kroger_upc
        qty, estimated = compute_purchase_qty(item.total_qty, item.total_unit, mapping.package_size)
        item.purchase_qty = qty
        item.purchase_qty_estimated = estimated
    db.flush()
```
Then call it at the very top of `get_match_state` (first line of the body):
```python
def get_match_state(db: Session) -> MatchRead:
    apply_remembered_products(db)
    draft = get_or_create_draft(db)
    ...
```
And at the top of `send_to_cart` (right after the existing `draft = get_or_create_draft(db)` line, before `token = ...`):
```python
    draft = get_or_create_draft(db)
    apply_remembered_products(db)
    token = kroger_auth.get_valid_token(db, client)
```

- [ ] **Step 4: Run, confirm PASS**

`uv run pytest tests/test_matching_apply.py -v`
Expected: PASS (all 5). Also run the existing matching tests to confirm no regression:
`uv run pytest tests/test_matching_service.py tests/test_matching_send.py tests/test_matching_router.py -q`

- [ ] **Step 5: Commit**
```bash
git add app/matching/service.py tests/test_matching_apply.py
git commit -m "feat(matching): apply_remembered_products auto-resolves picks from the map"
```

---

## Task 3: Preserve pantry decisions across `_recompute`

**Files:**
- Modify: `backend/app/consolidate/service.py` (`_recompute`)
- Test: `backend/tests/test_consolidate_pantry.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_consolidate_pantry.py`:
```python
from app.consolidate import service
from app.models import GroceryListItem, Ingredient, Recipe, RecipeIngredient


def _recipe(db, title, ingredient):
    r = Recipe(title=title, default_servings=2)
    db.add(r)
    db.flush()
    db.add(RecipeIngredient(recipe_id=r.id, raw_text="1 cup flour", qty=1.0, unit="cup",
                            ingredient_id=ingredient.id, parse_source="library", needs_review=False))
    db.flush()
    return r


def test_recompute_preserves_pantry_decision(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(flour)
    db_session.flush()
    r1 = _recipe(db_session, "Pancakes", flour)
    service.add_recipe(db_session, r1.id, 2)

    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    item.pantry_status = "skipped"
    item.pantry_resolved = True
    db_session.flush()

    # Adding another recipe triggers a full _recompute (delete + rebuild).
    r2 = _recipe(db_session, "Bread", flour)
    service.add_recipe(db_session, r2.id, 2)

    rebuilt = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert rebuilt.pantry_status == "skipped"
    assert rebuilt.pantry_resolved is True


def test_recompute_new_ingredient_starts_needed_unresolved(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(flour)
    db_session.flush()
    r1 = _recipe(db_session, "Pancakes", flour)
    service.add_recipe(db_session, r1.id, 2)
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert item.pantry_status == "needed"
    assert item.pantry_resolved is False
```

- [ ] **Step 2: Run, confirm FAIL**

`export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_consolidate_pantry.py -v`
Expected: `test_recompute_preserves_pantry_decision` FAILS (decision wiped to "needed"/false); the second test passes already.

- [ ] **Step 3: Implement snapshot/restore** — in `backend/app/consolidate/service.py`, modify `_recompute`. Add the snapshot right after the docstring (before the delete), and use it when building items:
```python
def _recompute(db: Session, draft: GroceryList) -> None:
    """Delete the list's items and rebuild them from its recipe memberships."""
    # Preserve per-ingredient user pantry decisions across the delete-and-rebuild.
    prior = {
        it.ingredient_id: (it.pantry_status, it.pantry_resolved)
        for it in db.execute(
            select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
        ).scalars().all()
    }

    db.execute(delete(GroceryListItem).where(GroceryListItem.list_id == draft.id))
```
Then in the item-creation loop, replace the `GroceryListItem(...)` construction's `pantry_status="needed",` line with restored values:
```python
    for ingredient_id, data in grouped.items():
        quantities = consolidate(data["quantities"])
        single = quantities[0] if len(quantities) == 1 else None
        status, resolved = prior.get(ingredient_id, ("needed", False))
        db.add(
            GroceryListItem(
                list_id=draft.id,
                ingredient_id=ingredient_id,
                quantities=quantities,
                total_qty=single["qty"] if single else None,
                total_unit=single["unit"] if single else None,
                source_recipe_ids=sorted(data["recipes"]),
                pantry_status=status,
                pantry_resolved=resolved,
            )
        )
    db.flush()
```

- [ ] **Step 4: Run, confirm PASS**

`uv run pytest tests/test_consolidate_pantry.py -v`
Then the existing consolidate suite: `uv run pytest tests/test_consolidate_service.py tests/test_consolidate_router.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**
```bash
git add app/consolidate/service.py tests/test_consolidate_pantry.py
git commit -m "feat(consolidate): preserve pantry decisions across list rebuild"
```

---

## Task 4: `pantry/` schemas + service

**Files:**
- Create: `backend/app/pantry/__init__.py` (empty)
- Create: `backend/app/pantry/schemas.py`, `backend/app/pantry/service.py`
- Test: `backend/tests/test_pantry_service.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_pantry_service.py`:
```python
from datetime import datetime, timedelta, timezone

import pytest

from app.pantry import service
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    PurchaseLog,
)


def _draft_item(db, *, status="needed", resolved=False):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=2.0, total_unit="lb",
                           pantry_status=status, pantry_resolved=resolved)
    db.add(item)
    db.flush()
    return gl, ing, item


def _purchase(db, ingredient_id, days_ago, qty=2.0, unit="lb"):
    db.add(PurchaseLog(ingredient_id=ingredient_id, kroger_upc="0001", qty=qty, unit=unit,
                       purchased_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
    db.flush()


def test_evaluate_flags_recent_purchase(db_session):
    gl, ing, item = _draft_item(db_session)
    _purchase(db_session, ing.id, days_ago=6)
    service.evaluate(db_session)
    assert item.pantry_status == "maybe_have"


def test_evaluate_ignores_old_purchase(db_session):
    gl, ing, item = _draft_item(db_session)
    _purchase(db_session, ing.id, days_ago=60)
    service.evaluate(db_session)
    assert item.pantry_status == "needed"


def test_evaluate_skips_resolved_items(db_session):
    gl, ing, item = _draft_item(db_session, resolved=True)
    _purchase(db_session, ing.id, days_ago=3)
    service.evaluate(db_session)
    assert item.pantry_status == "needed"


def test_get_view_includes_prompt_data_for_flagged(db_session):
    gl, ing, item = _draft_item(db_session)
    _purchase(db_session, ing.id, days_ago=6, qty=5.0, unit="lb")
    view = service.get_view(db_session)
    flagged = next(i for i in view.items if i.item_id == item.id)
    assert flagged.pantry_status == "maybe_have"
    assert flagged.last_qty == 5.0
    assert flagged.last_unit == "lb"
    assert flagged.days_ago == 6


def test_set_decision_keep(db_session):
    gl, ing, item = _draft_item(db_session, status="maybe_have")
    service.set_decision(db_session, item.id, keep=True)
    assert item.pantry_status == "needed"
    assert item.pantry_resolved is True


def test_set_decision_skip(db_session):
    gl, ing, item = _draft_item(db_session, status="maybe_have")
    service.set_decision(db_session, item.id, keep=False)
    assert item.pantry_status == "skipped"
    assert item.pantry_resolved is True


def test_set_decision_unknown_item_raises(db_session):
    with pytest.raises(service.ItemNotFoundError):
        service.set_decision(db_session, 9999, keep=True)
```

- [ ] **Step 2: Run, confirm FAIL**

`export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_pantry_service.py -v`
Expected: FAIL — `app.pantry.service` missing.

- [ ] **Step 3: Create `backend/app/pantry/__init__.py`** (empty), then **`backend/app/pantry/schemas.py`**:
```python
"""Pydantic models for the pantry 'still have it?' API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PantryItemRead(BaseModel):
    item_id: int
    ingredient_id: int
    ingredient_name: str | None
    pantry_status: str
    last_qty: float | None = None
    last_unit: str | None = None
    purchased_at: datetime | None = None
    days_ago: int | None = None


class PantryView(BaseModel):
    items: list[PantryItemRead]


class PantryDecisionRequest(BaseModel):
    keep: bool
```

- [ ] **Step 4: Create `backend/app/pantry/service.py`**:
```python
"""Pantry 'still have it?' logic: flag recently-bought ingredients and record keep/skip
decisions. Pure DB — no Kroger/LLM. Reads the self-tracked purchase_log."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.consolidate.service import get_or_create_draft
from app.models import GroceryListItem, Ingredient, PurchaseLog
from app.pantry.schemas import PantryItemRead, PantryView


class ItemNotFoundError(Exception):
    """The grocery_list_item id does not exist."""


def _recent_window_start() -> datetime:
    from datetime import timedelta

    return datetime.now(timezone.utc) - timedelta(days=get_settings().pantry_recent_days)


def _last_purchase(db: Session, ingredient_id: int, since: datetime) -> PurchaseLog | None:
    return db.execute(
        select(PurchaseLog)
        .where(PurchaseLog.ingredient_id == ingredient_id, PurchaseLog.purchased_at >= since)
        .order_by(PurchaseLog.purchased_at.desc())
    ).scalars().first()


def evaluate(db: Session) -> None:
    """Flag needed+unresolved items as maybe_have when bought within the recent window."""
    since = _recent_window_start()
    draft = get_or_create_draft(db)
    items = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
    ).scalars().all()
    for item in items:
        if item.pantry_resolved or item.pantry_status != "needed":
            continue
        if _last_purchase(db, item.ingredient_id, since) is not None:
            item.pantry_status = "maybe_have"
    db.flush()


def get_view(db: Session) -> PantryView:
    """Run evaluation and return every draft item with its pantry state + prompt data."""
    evaluate(db)
    since = _recent_window_start()
    draft = get_or_create_draft(db)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    items = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
    ).scalars().all()

    out: list[PantryItemRead] = []
    now = datetime.now(timezone.utc)
    for item in items:
        last = (
            _last_purchase(db, item.ingredient_id, since)
            if item.pantry_status == "maybe_have"
            else None
        )
        out.append(
            PantryItemRead(
                item_id=item.id,
                ingredient_id=item.ingredient_id,
                ingredient_name=ing_by_id[item.ingredient_id].canonical_name,
                pantry_status=item.pantry_status,
                last_qty=last.qty if last else None,
                last_unit=last.unit if last else None,
                purchased_at=last.purchased_at if last else None,
                days_ago=(now - last.purchased_at).days if last else None,
            )
        )
    return PantryView(items=out)


def set_decision(db: Session, item_id: int, keep: bool) -> None:
    item = db.get(GroceryListItem, item_id)
    if item is None:
        raise ItemNotFoundError(f"grocery_list_item {item_id} not found")
    item.pantry_status = "needed" if keep else "skipped"
    item.pantry_resolved = True
    db.flush()
```

- [ ] **Step 5: Run, confirm PASS**

`uv run pytest tests/test_pantry_service.py -v`
Expected: PASS (all 7).

- [ ] **Step 6: Commit**
```bash
git add app/pantry/__init__.py app/pantry/schemas.py app/pantry/service.py tests/test_pantry_service.py
git commit -m "feat(pantry): evaluate recent purchases + keep/skip decisions"
```

---

## Task 5: `pantry/router.py` + register

**Files:**
- Create: `backend/app/pantry/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_pantry_router.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_pantry_router.py`:
```python
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.matching.service import _kept_items
from app.models import GroceryList, GroceryListItem, Ingredient, PurchaseLog


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed(db, *, days_ago=None):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=2.0, total_unit="lb",
                           pantry_status="needed")
    db.add(item)
    if days_ago is not None:
        db.add(PurchaseLog(ingredient_id=ing.id, kroger_upc="0001", qty=2.0, unit="lb",
                           purchased_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
    db.flush()
    return gl, ing, item


def test_get_pantry_flags_recent(db_session):
    gl, ing, item = _seed(db_session, days_ago=5)
    client = _client(db_session)
    body = client.get("/list/pantry").json()
    flagged = next(i for i in body["items"] if i["item_id"] == item.id)
    assert flagged["pantry_status"] == "maybe_have"
    assert flagged["days_ago"] == 5
    app.dependency_overrides.clear()


def test_post_pantry_skip_excludes_from_kept(db_session):
    gl, ing, item = _seed(db_session, days_ago=5)
    client = _client(db_session)
    resp = client.post(f"/list/items/{item.id}/pantry", json={"keep": False})
    assert resp.status_code == 200
    assert _kept_items(db_session, gl.id) == []  # skipped item dropped from kept
    app.dependency_overrides.clear()


def test_post_pantry_keep_resolves(db_session):
    gl, ing, item = _seed(db_session, days_ago=5)
    client = _client(db_session)
    resp = client.post(f"/list/items/{item.id}/pantry", json={"keep": True})
    assert resp.status_code == 200
    db_session.refresh(item)
    assert item.pantry_status == "needed"
    assert item.pantry_resolved is True
    app.dependency_overrides.clear()


def test_post_pantry_unknown_item_404(db_session):
    client = _client(db_session)
    resp = client.post("/list/items/9999/pantry", json={"keep": True})
    assert resp.status_code == 404
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run, confirm FAIL**

`export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_pantry_router.py -v`
Expected: FAIL — `app.pantry.router` missing.

- [ ] **Step 3: Create `backend/app/pantry/router.py`**:
```python
"""HTTP layer for pantry 'still have it?'. Thin; delegates to pantry.service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.pantry import service
from app.pantry.schemas import PantryDecisionRequest, PantryView

router = APIRouter(prefix="/list", tags=["pantry"])


@router.get("/pantry", response_model=PantryView)
def get_pantry(db: Session = Depends(get_db)):
    view = service.get_view(db)
    db.commit()
    return view


@router.post("/items/{item_id}/pantry", response_model=PantryView)
def decide(item_id: int, body: PantryDecisionRequest, db: Session = Depends(get_db)):
    try:
        service.set_decision(db, item_id, body.keep)
    except service.ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view
```

- [ ] **Step 4: Register in `backend/app/main.py`** — add near the other router imports:
```python
from app.pantry.router import router as pantry_router
```
and after `app.include_router(matching_router)`:
```python
app.include_router(pantry_router)
```

- [ ] **Step 5: Run, confirm PASS + full backend suite (backend completion checkpoint)**
```bash
uv run pytest tests/test_pantry_router.py -v
uv run pytest -q
```
Expected: pantry router tests pass; full suite green. Report the total count.

- [ ] **Step 6: Commit**
```bash
git add app/pantry/router.py app/main.py tests/test_pantry_router.py
git commit -m "feat(pantry): GET /list/pantry + POST /list/items/{id}/pantry endpoints"
```

---

## Task 6: Frontend — pantry API client + types

**Files:**
- Modify: `frontend/src/recipes/types.ts`
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/recipes/pantryApi.test.ts`

- [ ] **Step 1: Write failing test** `frontend/src/recipes/pantryApi.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import { getPantry, setPantryDecision } from "../api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  } as Response);
}

describe("pantry api", () => {
  it("getPantry calls /list/pantry", async () => {
    const f = mockFetch({ items: [] });
    await getPantry();
    expect(f.mock.calls[0][0]).toContain("/list/pantry");
  });

  it("setPantryDecision POSTs keep", async () => {
    const f = mockFetch({ items: [] });
    await setPantryDecision(5, false);
    expect(f.mock.calls[0][0]).toContain("/list/items/5/pantry");
    const body = JSON.parse((f.mock.calls[0][1]?.body as string) ?? "{}");
    expect(body.keep).toBe(false);
  });
});
```

- [ ] **Step 2: Run, confirm FAIL**

(from `frontend/`) `npm test -- pantryApi`
Expected: FAIL — imports don't exist.

- [ ] **Step 3: Add types** — append to `frontend/src/recipes/types.ts`:
```ts
export interface PantryItem {
  item_id: number;
  ingredient_id: number;
  ingredient_name: string | null;
  pantry_status: string;
  last_qty: number | null;
  last_unit: string | null;
  purchased_at: string | null;
  days_ago: number | null;
}

export interface PantryView {
  items: PantryItem[];
}
```

- [ ] **Step 4: Add API functions** — in `frontend/src/api.ts`, add `PantryView` to the existing `import type { ... } from "./recipes/types";` line, then append:
```ts
export async function getPantry(): Promise<PantryView> {
  return json<PantryView>(await fetch(`${BASE_URL}/list/pantry`));
}

export async function setPantryDecision(itemId: number, keep: boolean): Promise<PantryView> {
  const res = await fetch(`${BASE_URL}/list/items/${itemId}/pantry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keep }),
  });
  return json<PantryView>(res);
}
```

- [ ] **Step 5: Run, confirm PASS**

`npm test -- pantryApi`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/recipes/types.ts frontend/src/api.ts frontend/src/recipes/pantryApi.test.ts
git commit -m "feat(web): pantry api client + types"
```

---

## Task 7: Frontend — PantryCheck panel + embed in GroceryList

**Files:**
- Create: `frontend/src/recipes/PantryCheck.tsx`
- Test: `frontend/src/recipes/PantryCheck.test.tsx`
- Modify: `frontend/src/recipes/GroceryList.tsx`

- [ ] **Step 1: Write failing test** `frontend/src/recipes/PantryCheck.test.tsx`:
```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { PantryCheck } from "./PantryCheck";

afterEach(() => vi.restoreAllMocks());

const flagged = {
  items: [
    {
      item_id: 1, ingredient_id: 2, ingredient_name: "rice", pantry_status: "maybe_have",
      last_qty: 5, last_unit: "lb", purchased_at: "2026-06-15T00:00:00Z", days_ago: 6,
    },
  ],
};

describe("PantryCheck", () => {
  it("shows a still-have-it prompt for flagged items", async () => {
    vi.spyOn(api, "getPantry").mockResolvedValue(flagged);
    render(<PantryCheck />);
    expect(await screen.findByText(/still have it/i)).toBeInTheDocument();
    expect(screen.getByText(/rice/)).toBeInTheDocument();
  });

  it("skips an item via 'I have it'", async () => {
    vi.spyOn(api, "getPantry").mockResolvedValue(flagged);
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    render(<PantryCheck />);
    fireEvent.click(await screen.findByRole("button", { name: /i have it/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(1, false));
  });

  it("renders nothing when no items are flagged", async () => {
    vi.spyOn(api, "getPantry").mockResolvedValue({
      items: [{ item_id: 1, ingredient_id: 2, ingredient_name: "rice", pantry_status: "needed",
                last_qty: null, last_unit: null, purchased_at: null, days_ago: null }],
    });
    const { container } = render(<PantryCheck />);
    await waitFor(() => expect(api.getPantry).toHaveBeenCalled());
    expect(screen.queryByText(/still have it/i)).not.toBeInTheDocument();
    expect(container.querySelector("[data-testid='pantry-empty']")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run, confirm FAIL**

`npm test -- PantryCheck`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `frontend/src/recipes/PantryCheck.tsx`**:
```tsx
import { useEffect, useState } from "react";

import { getPantry, setPantryDecision } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Pill } from "../components/ui/Pill";
import type { PantryView } from "./types";

export function PantryCheck() {
  const [view, setView] = useState<PantryView | null>(null);

  useEffect(() => {
    getPantry().then(setView).catch(() => setView(null));
  }, []);

  async function decide(itemId: number, keep: boolean) {
    setView(await setPantryDecision(itemId, keep));
  }

  if (!view) return null;

  const flagged = view.items.filter((i) => i.pantry_status === "maybe_have");
  const skipped = view.items.filter((i) => i.pantry_status === "skipped");

  if (flagged.length === 0 && skipped.length === 0) {
    return <span data-testid="pantry-empty" className="hidden" />;
  }

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Still have it?</h3>
      <ul className="flex flex-col gap-2">
        {flagged.map((i) => (
          <li key={i.item_id} className="flex flex-wrap items-center gap-2 rounded-xl bg-tint-amber px-3 py-2">
            <strong className="text-heading">{i.ingredient_name}</strong>
            <span className="text-sm text-ink">
              bought {i.last_qty ?? "?"} {i.last_unit ?? ""}, {i.days_ago} days ago — still have it?
            </span>
            <span className="ml-auto flex gap-2">
              <Button variant="secondary" onClick={() => decide(i.item_id, true)}>Keep</Button>
              <Button variant="link" onClick={() => decide(i.item_id, false)}>I have it</Button>
            </span>
          </li>
        ))}
      </ul>
      {skipped.length > 0 && (
        <div className="text-sm text-muted">
          <span className="font-medium">Skipping (already have): </span>
          {skipped.map((i, idx) => (
            <span key={i.item_id}>
              {idx > 0 && ", "}
              {i.ingredient_name}
              <button className="ml-1 text-primary underline" onClick={() => decide(i.item_id, true)}>
                undo
              </button>
            </span>
          ))}
        </div>
      )}
      {flagged.length > 0 && <Pill tone="warning">Decide before sending to keep them in your cart</Pill>}
    </Card>
  );
}
```

- [ ] **Step 4: Run, confirm PASS**

`npm test -- PantryCheck`
Expected: PASS (3 tests).

- [ ] **Step 5: Embed in `frontend/src/recipes/GroceryList.tsx`** — add the import and render it between the Shopping list card and `<MatchAndSend />`. Add near the other recipe-screen imports:
```tsx
import { PantryCheck } from "./PantryCheck";
```
Then in the JSX, immediately after the closing `</Card>` of the "Shopping list" card and before `<MatchAndSend />`, add:
```tsx
          <PantryCheck />
```

- [ ] **Step 6: Run GroceryList tests (the embedded PantryCheck calls getPantry on mount)** — update `frontend/src/recipes/GroceryList.test.tsx`'s `beforeEach` to also mock `getPantry` so the existing tests don't hit a real fetch. Change the `beforeEach` block to:
```tsx
beforeEach(() => {
  vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
  vi.spyOn(api, "getPantry").mockResolvedValue({ items: [] });
});
```
Then run: `npm test -- recipes/GroceryList recipes/PantryCheck`
Expected: PASS.

- [ ] **Step 7: Commit**
```bash
git add frontend/src/recipes/PantryCheck.tsx frontend/src/recipes/PantryCheck.test.tsx frontend/src/recipes/GroceryList.tsx frontend/src/recipes/GroceryList.test.tsx
git commit -m "feat(web): pantry 'still have it?' panel on the grocery list"
```

---

## Task 8: Frontend — per-item "Change product" affordance

**Files:**
- Modify: `frontend/src/recipes/MatchAndSend.tsx`
- Modify: `frontend/src/recipes/MatchAndSend.test.tsx`

- [ ] **Step 1: Add a test** — append inside the `describe("MatchAndSend", ...)` block in `frontend/src/recipes/MatchAndSend.test.tsx`:
```tsx
it("shows the matched product and a Change action when already resolved", async () => {
  vi.spyOn(api, "getMatch").mockResolvedValue({
    connected: true,
    store_location_id: "L1",
    items: [
      {
        item_id: 1, ingredient_id: 2, ingredient_name: "flour",
        total_qty: 3, total_unit: "lb", purchase_qty: 3, purchase_qty_estimated: false,
        kroger_upc: "0001",
        current: { upc: "0001", description: "AP Flour", size: "5 lb", price: null, stock_level: null },
      },
    ],
  });
  render(<MatchAndSend />);
  expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /change/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run, confirm FAIL**

`npm test -- recipes/MatchAndSend`
Expected: the new test FAILS (button is always "Find product"; also the size isn't shown).

- [ ] **Step 3: Update the per-item product row** in `frontend/src/recipes/MatchAndSend.tsx` — replace the block:
```tsx
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-ink">
                {it.current ? `Product: ${it.current.description}` : "No product chosen"}
              </span>
              <Button variant="secondary" className="ml-auto" onClick={() => find(it.item_id, it.ingredient_name)}>
                Find product
              </Button>
            </div>
```
with:
```tsx
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-ink">
                {it.current
                  ? `Product: ${it.current.description}${it.current.size ? ` (${it.current.size})` : ""}`
                  : "No product chosen yet"}
              </span>
              <Button variant="secondary" className="ml-auto" onClick={() => find(it.item_id, it.ingredient_name)}>
                {it.current ? "Change" : "Find product"}
              </Button>
            </div>
```

- [ ] **Step 4: Run, confirm PASS**

`npm test -- recipes/MatchAndSend`
Expected: PASS (existing tests — whose `baseMatch` has `current: null` so the button stays "Find product" — plus the new "Change" test).

- [ ] **Step 5: Commit**
```bash
git add frontend/src/recipes/MatchAndSend.tsx frontend/src/recipes/MatchAndSend.test.tsx
git commit -m "feat(web): show matched product + per-item Change action"
```

---

## Task 9: Final verification

**Files:** (verification only)

- [ ] **Step 1: Full backend suite (isolated DB)**
```bash
cd backend
export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test
uv run pytest -q
```
Expected: all pass (existing + Phase 5 tests). Report the count.

- [ ] **Step 2: Full frontend suite + build**
```bash
cd frontend
npm test
npm run build
```
Expected: all tests pass; build clean.

- [ ] **Step 3: Confirm no stray issues**
```bash
cd backend && uv run python -c "from app.main import app; print('app imports ok')"
```
Expected: prints ok (all routers register without error).

- [ ] **Step 4: Commit any cleanup** (empty if nothing)
```bash
git commit --allow-empty -m "chore: Phase 5 final verification"
```

---

## Done criteria

- `uv run pytest -q` (backend, 5544) and `npm test` + `npm run build` (frontend) all green.
- Confirmed products auto-resolve on the match panel and survive recipe edits; any item can be changed (which updates the remembered map).
- Recently-bought items flag "still have it?"; keep/skip persists across recipe edits and never re-prompts.
- One migration (`pantry_resolved`); no new Kroger/LLM calls.
- Phase 5 merged to `master` via finishing-a-development-branch.

## Manual smoke test (optional, user-run)

After a real cart has been sent (so `purchase_log` has rows): rebuild a draft list containing a previously-bought ingredient → it flags "still have it?" on `/list`; an ingredient with a remembered product shows it pre-filled with a "Change" button. Rebuild the web container to see it: `docker compose up --build web`.

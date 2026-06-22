# Home Store Persistence + Saved Staples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the Kroger home store as a user-level setting (so it survives across drafts), and add a saved "staples" catalog whose items can auto-add to every trip and flow through the list like recipe ingredients.

**Architecture:** Part A — a single-row `app_settings` table holds the home store; `matching` reads/writes it there instead of the per-draft column. Part B — `staples` catalog + `grocery_list_staples` per-draft links (seeded once via `grocery_lists.staples_seeded`); `_recompute` folds linked staples into the list; a new `app/staples/` module owns the logic. No new Kroger/LLM calls beyond the existing `canonicalize` path for new staple names.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + Pydantic; React/TS + Vite + Tailwind + react-router; pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-06-21-bushel-store-staples-design.md`

**Conventions:**
- Backend from `backend/`, `uv run`. **Tests MUST export** `DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test` before `pytest`/`alembic`. **NEVER port 5432** (live dev DB; conftest drops all tables).
- Services flush; routers commit. The LLM client is provided via a router-local `get_llm()` dependency (see `recipes/router.py`); tests mock it.
- Frontend from `frontend/`: `npm test -- <pattern>`, `npm run build`. Warm Pantry primitives in `src/components/ui/`.
- Current Alembic head: `d4e5f6a7b8c9`. The two migrations below chain: A1 (`e5f6a7b8c9d0`) → B1 (`f6a7b8c9d0e1`).
- Parts A and B are independent; do A1–A3 then B1–B7.

---

## Task A1: `app_settings` table + settings module

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/migrations/versions/e5f6a7b8c9d0_add_app_settings.py`
- Create: `backend/app/settings/__init__.py` (empty), `backend/app/settings/service.py`
- Test: `backend/tests/test_settings_service.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_settings_service.py`:
```python
from app.settings import service
from app.models import AppSettings


def test_get_settings_row_creates_single_row(db_session):
    row1 = service.get_settings_row(db_session)
    row2 = service.get_settings_row(db_session)
    assert row1.id == row2.id
    assert db_session.query(AppSettings).count() == 1


def test_set_home_store_upserts(db_session):
    service.set_home_store(db_session, "L1", "Kroger Downtown")
    service.set_home_store(db_session, "L2", "Kroger Uptown")
    rows = db_session.query(AppSettings).all()
    assert len(rows) == 1
    assert rows[0].home_store_location_id == "L2"
    assert rows[0].home_store_name == "Kroger Uptown"


def test_get_home_store_returns_id_and_name(db_session):
    service.set_home_store(db_session, "L9", "Test Store")
    assert service.get_home_store(db_session) == ("L9", "Test Store")


def test_get_home_store_unset_returns_none(db_session):
    assert service.get_home_store(db_session) == (None, None)
```

- [ ] **Step 2: Run, confirm FAIL:** `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_settings_service.py -v`

- [ ] **Step 3: Add the model** — in `backend/app/models.py`, add (near the other models):
```python
class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    home_store_location_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    home_store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
```
(`Integer`, `String`, `Mapped`, `mapped_column` are already imported.)

- [ ] **Step 4: Migration** `backend/migrations/versions/e5f6a7b8c9d0_add_app_settings.py`:
```python
"""add app_settings

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-21 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'app_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('home_store_location_id', sa.String(length=50), nullable=True),
        sa.Column('home_store_name', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('app_settings')
```

- [ ] **Step 5: Create `backend/app/settings/__init__.py`** (empty) and `backend/app/settings/service.py`:
```python
"""Single-row app settings (home store, future prefs). Pure DB."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSettings


def get_settings_row(db: Session) -> AppSettings:
    row = db.execute(select(AppSettings)).scalars().first()
    if row is None:
        row = AppSettings()
        db.add(row)
        db.flush()
    return row


def set_home_store(db: Session, location_id: str, name: str | None) -> AppSettings:
    row = get_settings_row(db)
    row.home_store_location_id = location_id
    row.home_store_name = name
    db.flush()
    return row


def get_home_store(db: Session) -> tuple[str | None, str | None]:
    row = get_settings_row(db)
    return row.home_store_location_id, row.home_store_name
```

- [ ] **Step 6: Run, confirm PASS:** `uv run pytest tests/test_settings_service.py -v`

- [ ] **Step 7: Commit:**
```bash
git add app/models.py app/settings/__init__.py app/settings/service.py migrations/versions/e5f6a7b8c9d0_add_app_settings.py tests/test_settings_service.py
git commit -m "feat(settings): app_settings single-row table for home store"
```

---

## Task A2: Matching reads/writes the home store via settings

**Files:**
- Modify: `backend/app/matching/service.py`, `backend/app/matching/schemas.py`, `backend/app/matching/router.py`
- Test: `backend/tests/test_matching_home_store.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_matching_home_store.py`:
```python
from unittest.mock import MagicMock

import pytest

from app.kroger.schemas import Product, TokenResp
from app.matching import service
from app.models import GroceryList, GroceryListItem, Ingredient
from app.settings import service as settings_service


def _draft_with_item(db):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=3.0,
                           total_unit="lb", pantry_status="needed")
    db.add(item)
    db.flush()
    return gl, ing, item


def test_set_store_persists_to_settings_with_name(db_session):
    _draft_with_item(db_session)
    state = service.set_store(db_session, "L1", "Kroger Downtown")
    assert state.store_location_id == "L1"
    assert state.store_name == "Kroger Downtown"
    assert settings_service.get_home_store(db_session) == ("L1", "Kroger Downtown")


def test_home_store_persists_across_new_draft(db_session):
    gl, ing, item = _draft_with_item(db_session)
    service.set_store(db_session, "L1", "Kroger Downtown")
    # Simulate a fresh trip: mark the draft sent so get_or_create_draft makes a new one.
    gl.status = "sent_to_kroger"
    db_session.flush()
    state = service.get_match_state(db_session)
    assert state.store_location_id == "L1"  # home store still applies to the new draft
    assert state.store_name == "Kroger Downtown"


def test_search_uses_settings_home_store(db_session):
    gl, ing, item = _draft_with_item(db_session)
    settings_service.set_home_store(db_session, "L1", "Kroger Downtown")
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = [Product(upc="0001", description="Flour")]
    service.search_item_products(db_session, kroger, item.id, query=None)
    kroger.search_products.assert_called_once_with("ct", "flour", "L1")


def test_search_no_home_store_raises(db_session):
    gl, ing, item = _draft_with_item(db_session)
    with pytest.raises(service.NoStoreSelectedError):
        service.search_item_products(db_session, MagicMock(), item.id, query=None)
```

- [ ] **Step 2: Run, confirm FAIL:** `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_matching_home_store.py -v`

- [ ] **Step 3: Add `store_name` to `MatchRead`** in `backend/app/matching/schemas.py` — in the `MatchRead` model, add a field after `store_location_id`:
```python
    store_name: str | None = None
```
And add `name` to `SetStoreRequest`:
```python
class SetStoreRequest(BaseModel):
    location_id: str
    name: str | None = None
```

- [ ] **Step 4: Update `matching/service.py`** — add the import at the top (next to other imports):
```python
from app.settings import service as settings_service
```
Replace `set_store`:
```python
def set_store(db: Session, location_id: str, name: str | None = None) -> MatchRead:
    """Persist the chosen Kroger store as the user's home store, then return match state."""
    settings_service.set_home_store(db, location_id, name)
    return get_match_state(db)
```
In `get_match_state`, replace the `return MatchRead(...)` block so the store comes from settings:
```python
    loc, store_name = settings_service.get_home_store(db)
    return MatchRead(
        connected=kroger_auth.get_auth(db) is not None,
        store_location_id=loc,
        store_name=store_name,
        items=items,
    )
```
In `search_item_products`, replace the store lookup. Change:
```python
    item = _get_item(db, item_id)
    gl = db.get(GroceryList, item.list_id)
    if gl is None or gl.store_location_id is None:
        raise NoStoreSelectedError("pick a store before searching products")

    ingredient = db.get(Ingredient, item.ingredient_id)
    term = query or (ingredient.canonical_name if ingredient else "")
    token = client.fetch_client_token()
    products = client.search_products(token.access_token, term, gl.store_location_id)
```
to:
```python
    item = _get_item(db, item_id)
    location_id, _name = settings_service.get_home_store(db)
    if location_id is None:
        raise NoStoreSelectedError("pick a store before searching products")

    ingredient = db.get(Ingredient, item.ingredient_id)
    term = query or (ingredient.canonical_name if ingredient else "")
    token = client.fetch_client_token()
    products = client.search_products(token.access_token, term, location_id)
```
(`GroceryList` may now be unused in that function but is still imported/used elsewhere in the file — leave the import.)

- [ ] **Step 5: Update `matching/router.py`** `set_store` endpoint to pass the name:
```python
@router.post("/store", response_model=MatchRead)
def set_store(body: SetStoreRequest, db: Session = Depends(get_db)):
    state = service.set_store(db, body.location_id, body.name)
    db.commit()
    return state
```

- [ ] **Step 6: Run, confirm PASS, and fix the regression ripple.** The store now comes from `app_settings`, not the draft, so **pre-existing tests that seeded the store on the draft `GroceryList` (`store_location_id="L1"`) will break** — they need the home store seeded via settings instead. Run:
```bash
uv run pytest tests/test_matching_home_store.py -v
uv run pytest tests/test_matching_service.py tests/test_matching_apply.py tests/test_matching_send.py tests/test_matching_router.py -q
```
Expected breakers and fixes (apply to each that fails):
- `test_matching_service.py::test_get_match_state_reports_items_and_store` — it asserts `state.store_location_id == "L1"` from a draft-set store. Add `from app.settings import service as settings_service` and seed `settings_service.set_home_store(db_session, "L1", None)` before calling `get_match_state`; keep the assertion.
- `test_matching_service.py::test_search_item_products_uses_store_and_canonical_name` — seed `settings_service.set_home_store(db_session, "L1", None)` instead of relying on the draft's `store_location_id`.
- `test_matching_router.py::test_search_products_endpoint` and `test_search_products_auth_error_is_502` — these `_seed` a draft store; the search now needs the home store in settings. In each, seed `settings_service.set_home_store(db_session, "L1", None)` before the request (the auth-error test still reaches the 502 because the store is now set).
- `test_set_store_endpoint` posts `{"location_id": "L42"}` and asserts `store_location_id == "L42"` — still passes (settings stores L42).
Fix every failure by seeding the store via `settings_service.set_home_store`, never by re-adding a draft column dependency. Re-run until all green; report which tests you changed.

- [ ] **Step 7: Commit:**
```bash
git add app/matching/service.py app/matching/schemas.py app/matching/router.py tests/test_matching_home_store.py
git commit -m "feat(matching): read/write home store via app_settings (persists across drafts)"
```

---

## Task A3: Frontend — home store name + persistence

**Files:**
- Modify: `frontend/src/api.ts`, `frontend/src/recipes/types.ts`, `frontend/src/recipes/KrogerSetup.tsx`, `frontend/src/recipes/KrogerSetup.test.tsx`

- [ ] **Step 1: Update the API + types.** In `frontend/src/recipes/types.ts`, add `store_name` to `MatchData` (optional so other mocks don't break):
```ts
// inside interface MatchData, add:
  store_name?: string | null;
```
In `frontend/src/api.ts`, change `setStore` to send a name:
```ts
export async function setStore(locationId: string, name?: string | null): Promise<MatchData> {
  const res = await fetch(`${BASE_URL}/list/store`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ location_id: locationId, name: name ?? null }),
  });
  return json<MatchData>(res);
}
```

- [ ] **Step 2: Update `KrogerSetup.test.tsx`** (the store is now shown by name as "Home store: …"). Replace the "selects a store" and "hydrates" tests:
```tsx
  it("selects a store and shows its name", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: false });
    vi.spyOn(api, "searchLocations").mockResolvedValue([
      { location_id: "L1", name: "Kroger Downtown", address: "1 Main St" },
    ]);
    const set = vi.spyOn(api, "setStore").mockResolvedValue({
      connected: true, store_location_id: "L1", store_name: "Kroger Downtown", items: [],
    });
    render(<KrogerSetup />);
    fireEvent.change(await screen.findByLabelText(/zip/i), { target: { value: "45202" } });
    fireEvent.click(screen.getByRole("button", { name: /find stores/i }));
    fireEvent.click(await screen.findByRole("button", { name: /use this store/i }));
    await waitFor(() => expect(set).toHaveBeenCalledWith("L1", "Kroger Downtown"));
    expect(await screen.findByText(/Home store: Kroger Downtown/)).toBeInTheDocument();
  });

  it("hydrates the home store name on mount", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: false });
    vi.spyOn(api, "getMatch").mockResolvedValue({
      connected: true, store_location_id: "L7", store_name: "Kroger Eastgate", items: [],
    });
    render(<KrogerSetup />);
    expect(await screen.findByText(/Home store: Kroger Eastgate/)).toBeInTheDocument();
  });
```
(Keep the other two tests as-is. The `beforeEach` getMatch mock — add `store_name: null` to it for type completeness, though optional makes it unnecessary.)

- [ ] **Step 3: Run, confirm FAIL:** `npm test -- KrogerSetup`

- [ ] **Step 4: Update `KrogerSetup.tsx`** — track the store name and pass it to `setStore`. Replace the relevant parts: the `selected` state now holds the name; hydrate from `store_name`; `choose` takes the location object:
```tsx
  const [selectedName, setSelectedName] = useState<string | null>(null);
```
(replace the `const [selected, setSelected] = useState<string | null>(null);` line)

Replace the mount effect's getMatch line:
```tsx
    getMatch().then((m) => setSelectedName(m.store_name ?? null)).catch(() => {});
```
Replace `choose`:
```tsx
  async function choose(loc: KrogerLocation) {
    const match = await setStore(loc.location_id, loc.name);
    setSelectedName(match.store_name ?? null);
  }
```
Replace the "Selected store" line:
```tsx
        {selectedName && <p className="text-sm text-success">Home store: {selectedName}</p>}
```
Replace the store-list button onClick:
```tsx
              <Button variant="secondary" className="ml-auto" onClick={() => choose(s)}>
                Use this store
              </Button>
```

- [ ] **Step 5: Run, confirm PASS + build:** `npm test -- KrogerSetup` then `npm run build`. Also run the full frontend suite to confirm the optional `store_name` didn't break other getMatch mocks: `npm test`.

- [ ] **Step 6: Commit:**
```bash
git add src/api.ts src/recipes/types.ts src/recipes/KrogerSetup.tsx src/recipes/KrogerSetup.test.tsx
git commit -m "feat(web): show + persist home store by name"
```

---

## Task B1: Staples models + migration

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/migrations/versions/f6a7b8c9d0e1_add_staples.py`
- Test: `backend/tests/test_models.py` (append)

- [ ] **Step 1: Write failing test** — append to `backend/tests/test_models.py`:
```python
def test_staple_and_link_models(db_session):
    from app.models import GroceryList, GroceryListStaple, Ingredient, Staple

    ing = Ingredient(canonical_name="peanut butter", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    staple = Staple(ingredient_id=ing.id)
    db_session.add(staple)
    db_session.flush()
    assert staple.auto_add is True

    gl = GroceryList(name="Draft", status="draft")
    db_session.add(gl)
    db_session.flush()
    assert gl.staples_seeded is False
    db_session.add(GroceryListStaple(list_id=gl.id, staple_id=staple.id))
    db_session.flush()
```

- [ ] **Step 2: Run, confirm FAIL:** `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_models.py::test_staple_and_link_models -v`

- [ ] **Step 3: Add models** to `backend/app/models.py`:
```python
class Staple(Base):
    __tablename__ = "staples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), unique=True
    )
    auto_add: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GroceryListStaple(Base):
    __tablename__ = "grocery_list_staples"
    __table_args__ = (UniqueConstraint("list_id", "staple_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"))
    staple_id: Mapped[int] = mapped_column(ForeignKey("staples.id", ondelete="CASCADE"))
```
(`ForeignKey`, `UniqueConstraint`, `Boolean`, `Integer` are already imported — `UniqueConstraint` is used by `GroceryListRecipe`.)
And add `staples_seeded` to `class GroceryList` (after `sent_at`):
```python
    staples_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: Migration** `backend/migrations/versions/f6a7b8c9d0e1_add_staples.py`:
```python
"""add staples + grocery_list_staples + staples_seeded

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-21 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'staples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ingredient_id', sa.Integer(), nullable=False),
        sa.Column('auto_add', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ingredient_id'),
    )
    op.create_table(
        'grocery_list_staples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('staple_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['list_id'], ['grocery_lists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staple_id'], ['staples.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('list_id', 'staple_id'),
    )
    op.add_column(
        'grocery_lists',
        sa.Column('staples_seeded', sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('grocery_lists', 'staples_seeded')
    op.drop_table('grocery_list_staples')
    op.drop_table('staples')
```

- [ ] **Step 5: Run, confirm PASS:** `uv run pytest tests/test_models.py::test_staple_and_link_models -v`

- [ ] **Step 6: Commit:**
```bash
git add app/models.py migrations/versions/f6a7b8c9d0e1_add_staples.py tests/test_models.py
git commit -m "feat(db): staples + grocery_list_staples tables + staples_seeded"
```

---

## Task B2: consolidate `recompute_draft` + `_recompute` folds staples

**Files:**
- Modify: `backend/app/consolidate/service.py`
- Test: `backend/tests/test_consolidate_staples.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_consolidate_staples.py`:
```python
from app.consolidate import service
from app.models import (
    GroceryListItem,
    GroceryListStaple,
    Ingredient,
    Recipe,
    RecipeIngredient,
    Staple,
)


def _recipe(db, title, ingredient):
    r = Recipe(title=title, default_servings=2)
    db.add(r)
    db.flush()
    db.add(RecipeIngredient(recipe_id=r.id, raw_text="1 cup flour", qty=1.0, unit="cup",
                            ingredient_id=ingredient.id, parse_source="library", needs_review=False))
    db.flush()
    return r


def test_recompute_includes_linked_staple_as_item(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[], category="baking")
    pb = Ingredient(canonical_name="peanut butter", aliases=[], category="pantry")
    db_session.add_all([flour, pb])
    db_session.flush()
    r = _recipe(db_session, "Pancakes", flour)
    service.add_recipe(db_session, r.id, 2)

    staple = Staple(ingredient_id=pb.id)
    db_session.add(staple)
    db_session.flush()
    draft = service.get_or_create_draft(db_session)
    db_session.add(GroceryListStaple(list_id=draft.id, staple_id=staple.id))
    db_session.flush()

    service.recompute_draft(db_session)
    ids = {it.ingredient_id for it in db_session.query(GroceryListItem).filter_by(list_id=draft.id)}
    assert pb.id in ids  # the staple became a shopping-list item
    assert flour.id in ids


def test_recompute_staple_only_item_has_empty_sources(db_session):
    pb = Ingredient(canonical_name="peanut butter", aliases=[], category="pantry")
    db_session.add(pb)
    db_session.flush()
    draft = service.get_or_create_draft(db_session)
    staple = Staple(ingredient_id=pb.id)
    db_session.add(staple)
    db_session.flush()
    db_session.add(GroceryListStaple(list_id=draft.id, staple_id=staple.id))
    db_session.flush()

    service.recompute_draft(db_session)
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=pb.id).one()
    assert item.source_recipe_ids == []
```

- [ ] **Step 2: Run, confirm FAIL:** `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_consolidate_staples.py -v`

- [ ] **Step 3: Update `backend/app/consolidate/service.py`.** Extend the models import to include the staple models:
```python
from app.models import (
    GroceryList,
    GroceryListItem,
    GroceryListRecipe,
    GroceryListStaple,
    Recipe,
    RecipeIngredient,
    Staple,
)
```
In `_recompute`, after the membership `for m in memberships:` loop finishes building `grouped` (and before the `for ingredient_id, data in grouped.items():` item-creation loop), insert:
```python
    # Fold in this draft's saved staples as "as needed" quantities (qty None).
    staple_links = db.execute(
        select(GroceryListStaple).where(GroceryListStaple.list_id == draft.id)
    ).scalars().all()
    if staple_links:
        staple_by_id = {s.id: s for s in db.execute(select(Staple)).scalars().all()}
        for link in staple_links:
            staple = staple_by_id.get(link.staple_id)
            if staple is not None:
                grouped[staple.ingredient_id]["quantities"].append((None, None))
```
Then add a public wrapper at the end of the file:
```python
def recompute_draft(db: Session) -> GroceryList:
    """Public entry point to rebuild the active draft's items (used by staples)."""
    draft = get_or_create_draft(db)
    _recompute(db, draft)
    return draft
```

- [ ] **Step 4: Run, confirm PASS + regression:**
```bash
uv run pytest tests/test_consolidate_staples.py -v
uv run pytest tests/test_consolidate_service.py tests/test_consolidate_router.py tests/test_consolidate_pantry.py -q
```

- [ ] **Step 5: Commit:**
```bash
git add app/consolidate/service.py tests/test_consolidate_staples.py
git commit -m "feat(consolidate): fold linked staples into the list + recompute_draft"
```

---

## Task B3: staples service + schemas

**Files:**
- Create: `backend/app/staples/__init__.py` (empty), `backend/app/staples/schemas.py`, `backend/app/staples/service.py`
- Test: `backend/tests/test_staples_service.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_staples_service.py`:
```python
from unittest.mock import MagicMock

import pytest

from app.consolidate.service import get_or_create_draft
from app.ingredients.canonicalize import CanonResult
from app.models import GroceryListStaple, Ingredient, Staple
from app.staples import service


def _ingredient(db, name="peanut butter"):
    ing = Ingredient(canonical_name=name, aliases=[], category="pantry")
    db.add(ing)
    db.flush()
    return ing


def _llm_for(ingredient_id):
    # add_staple calls canonicalize_names([name], db, llm); patch it via the service module.
    return MagicMock()


def test_add_staple_creates_for_resolved_ingredient(db_session, monkeypatch):
    ing = _ingredient(db_session)
    monkeypatch.setattr(service, "canonicalize_names",
                        lambda names, db, llm: {names[0]: CanonResult(ingredient_id=ing.id, is_new=False)})
    s = service.add_staple(db_session, "peanut butter", MagicMock())
    assert s.ingredient_id == ing.id
    assert db_session.query(Staple).count() == 1


def test_add_staple_is_idempotent_per_ingredient(db_session, monkeypatch):
    ing = _ingredient(db_session)
    monkeypatch.setattr(service, "canonicalize_names",
                        lambda names, db, llm: {names[0]: CanonResult(ingredient_id=ing.id, is_new=False)})
    service.add_staple(db_session, "peanut butter", MagicMock())
    service.add_staple(db_session, "peanut butter", MagicMock())
    assert db_session.query(Staple).count() == 1


def test_set_auto_add_and_remove(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id)
    db_session.add(s)
    db_session.flush()
    service.set_auto_add(db_session, s.id, False)
    assert s.auto_add is False
    service.remove_staple(db_session, s.id)
    assert db_session.query(Staple).count() == 0


def test_sync_draft_seeds_auto_staples_once(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id, auto_add=True)
    db_session.add(s)
    db_session.flush()
    draft = get_or_create_draft(db_session)

    service.sync_draft(db_session, draft)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id).count() == 1
    assert draft.staples_seeded is True

    # Remove it from the trip; re-sync must NOT re-add (seed runs once).
    service.remove_from_trip(db_session, s.id)
    service.sync_draft(db_session, draft)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id).count() == 0


def test_add_and_remove_from_trip(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id, auto_add=False)
    db_session.add(s)
    db_session.flush()
    service.add_to_trip(db_session, s.id)
    draft = get_or_create_draft(db_session)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id, staple_id=s.id).count() == 1
    service.remove_from_trip(db_session, s.id)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id, staple_id=s.id).count() == 0


def test_get_view_reports_on_trip_and_auto(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id, auto_add=True)
    db_session.add(s)
    db_session.flush()
    view = service.get_view(db_session)  # runs sync_draft → auto staple linked
    row = next(r for r in view.staples if r.id == s.id)
    assert row.ingredient_name == "peanut butter"
    assert row.auto_add is True
    assert row.on_trip is True


def test_remove_staple_unknown_raises(db_session):
    with pytest.raises(service.StapleNotFoundError):
        service.remove_staple(db_session, 9999)
```

- [ ] **Step 2: Run, confirm FAIL:** `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_staples_service.py -v`

- [ ] **Step 3: Create `backend/app/staples/__init__.py`** (empty) and `backend/app/staples/schemas.py`:
```python
"""Pydantic models for the staples API."""

from __future__ import annotations

from pydantic import BaseModel


class StapleRead(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str | None
    auto_add: bool
    on_trip: bool


class StapleView(BaseModel):
    staples: list[StapleRead]


class AddStapleRequest(BaseModel):
    name: str


class AutoAddRequest(BaseModel):
    auto_add: bool
```

- [ ] **Step 4: Create `backend/app/staples/service.py`:**
```python
"""Saved staples catalog + per-trip links. Pure DB except canonicalize (LLM) for new names."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consolidate.service import get_or_create_draft, recompute_draft
from app.ingredients.canonicalize import canonicalize_names
from app.llm.client import LLMClient
from app.models import GroceryListStaple, Ingredient, Staple
from app.staples.schemas import StapleRead, StapleView


class StapleNotFoundError(Exception):
    """The staple id does not exist."""


def _get_staple(db: Session, staple_id: int) -> Staple:
    s = db.get(Staple, staple_id)
    if s is None:
        raise StapleNotFoundError(f"staple {staple_id} not found")
    return s


def add_staple(db: Session, name: str, llm: LLMClient) -> Staple:
    """Resolve the name to a canonical ingredient and save it as a staple (one per ingredient)."""
    result = canonicalize_names([name], db, llm)[name]
    existing = db.execute(
        select(Staple).where(Staple.ingredient_id == result.ingredient_id)
    ).scalars().first()
    if existing is not None:
        return existing
    staple = Staple(ingredient_id=result.ingredient_id)
    db.add(staple)
    db.flush()
    return staple


def remove_staple(db: Session, staple_id: int) -> None:
    staple = _get_staple(db, staple_id)
    db.delete(staple)
    db.flush()
    recompute_draft(db)


def set_auto_add(db: Session, staple_id: int, auto_add: bool) -> None:
    staple = _get_staple(db, staple_id)
    staple.auto_add = auto_add
    db.flush()


def _link(db: Session, list_id: int, staple_id: int) -> GroceryListStaple | None:
    return db.execute(
        select(GroceryListStaple).where(
            GroceryListStaple.list_id == list_id, GroceryListStaple.staple_id == staple_id
        )
    ).scalars().first()


def sync_draft(db: Session, draft) -> None:
    """Seed auto_add staples onto the draft once (idempotent thereafter)."""
    if draft.staples_seeded:
        return
    autos = db.execute(select(Staple).where(Staple.auto_add.is_(True))).scalars().all()
    for s in autos:
        if _link(db, draft.id, s.id) is None:
            db.add(GroceryListStaple(list_id=draft.id, staple_id=s.id))
    draft.staples_seeded = True
    db.flush()
    if autos:
        recompute_draft(db)


def add_to_trip(db: Session, staple_id: int) -> None:
    _get_staple(db, staple_id)
    draft = get_or_create_draft(db)
    if _link(db, draft.id, staple_id) is None:
        db.add(GroceryListStaple(list_id=draft.id, staple_id=staple_id))
        db.flush()
        recompute_draft(db)


def remove_from_trip(db: Session, staple_id: int) -> None:
    draft = get_or_create_draft(db)
    link = _link(db, draft.id, staple_id)
    if link is not None:
        db.delete(link)
        db.flush()
        recompute_draft(db)


def get_view(db: Session) -> StapleView:
    draft = get_or_create_draft(db)
    sync_draft(db, draft)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    on_trip_ids = {
        l.staple_id
        for l in db.execute(
            select(GroceryListStaple).where(GroceryListStaple.list_id == draft.id)
        ).scalars().all()
    }
    staples = db.execute(select(Staple).order_by(Staple.id)).scalars().all()
    return StapleView(
        staples=[
            StapleRead(
                id=s.id,
                ingredient_id=s.ingredient_id,
                ingredient_name=ing_by_id[s.ingredient_id].canonical_name
                if s.ingredient_id in ing_by_id
                else None,
                auto_add=s.auto_add,
                on_trip=s.id in on_trip_ids,
            )
            for s in staples
        ]
    )
```
Note: `CanonResult` (returned by `canonicalize_names`) has an `ingredient_id` attribute — confirm by reading `app/ingredients/canonicalize.py` if unsure.

- [ ] **Step 5: Run, confirm PASS:** `uv run pytest tests/test_staples_service.py -v`

- [ ] **Step 6: Commit:**
```bash
git add app/staples/__init__.py app/staples/schemas.py app/staples/service.py tests/test_staples_service.py
git commit -m "feat(staples): catalog + per-trip links + seed-once sync"
```

---

## Task B4: staples router + register

**Files:**
- Create: `backend/app/staples/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_staples_router.py`

- [ ] **Step 1: Write failing tests** `backend/tests/test_staples_router.py`:
```python
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.ingredients.canonicalize import CanonResult
from app.main import app
from app.models import Ingredient, Staple
from app.staples import service as staples_service
from app.staples.router import get_llm


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_llm] = lambda: MagicMock()
    return TestClient(app)


def test_add_and_list_staples(db_session, monkeypatch):
    ing = Ingredient(canonical_name="peanut butter", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    monkeypatch.setattr(staples_service, "canonicalize_names",
                        lambda names, db, llm: {names[0]: CanonResult(ingredient_id=ing.id, is_new=False)})
    client = _client(db_session)
    resp = client.post("/staples", json={"name": "peanut butter"})
    assert resp.status_code == 200
    body = client.get("/list/staples").json()
    assert any(s["ingredient_name"] == "peanut butter" for s in body["staples"])
    app.dependency_overrides.clear()


def test_toggle_auto_add_and_remove(db_session):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    s = Staple(ingredient_id=ing.id)
    db_session.add(s)
    db_session.flush()
    client = _client(db_session)
    assert client.patch(f"/staples/{s.id}", json={"auto_add": False}).status_code == 200
    db_session.refresh(s)
    assert s.auto_add is False
    assert client.delete(f"/staples/{s.id}").status_code == 200
    assert client.delete(f"/staples/{s.id}").status_code == 404
    app.dependency_overrides.clear()


def test_add_remove_on_trip(db_session):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db_session.add(ing)
    db_session.flush()
    s = Staple(ingredient_id=ing.id, auto_add=False)
    db_session.add(s)
    db_session.flush()
    client = _client(db_session)
    assert client.post(f"/list/staples/{s.id}").status_code == 200
    body = client.get("/list/staples").json()
    assert next(x for x in body["staples"] if x["id"] == s.id)["on_trip"] is True
    assert client.delete(f"/list/staples/{s.id}").status_code == 200
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run, confirm FAIL:** `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test && uv run pytest tests/test_staples_router.py -v`

- [ ] **Step 3: Create `backend/app/staples/router.py`:**
```python
"""HTTP layer for the staples catalog + per-trip membership."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.client import LLMClient
from app.staples import service
from app.staples.schemas import AddStapleRequest, AutoAddRequest, StapleView

router = APIRouter(tags=["staples"])


def get_llm() -> LLMClient:
    return LLMClient()


@router.get("/list/staples", response_model=StapleView)
def list_staples(db: Session = Depends(get_db)):
    view = service.get_view(db)
    db.commit()
    return view


@router.post("/staples", response_model=StapleView)
def add_staple(body: AddStapleRequest, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    service.add_staple(db, body.name, llm)
    view = service.get_view(db)
    db.commit()
    return view


@router.delete("/staples/{staple_id}", response_model=StapleView)
def remove_staple(staple_id: int, db: Session = Depends(get_db)):
    try:
        service.remove_staple(db, staple_id)
    except service.StapleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view


@router.patch("/staples/{staple_id}", response_model=StapleView)
def set_auto_add(staple_id: int, body: AutoAddRequest, db: Session = Depends(get_db)):
    try:
        service.set_auto_add(db, staple_id, body.auto_add)
    except service.StapleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view


@router.post("/list/staples/{staple_id}", response_model=StapleView)
def add_to_trip(staple_id: int, db: Session = Depends(get_db)):
    try:
        service.add_to_trip(db, staple_id)
    except service.StapleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    view = service.get_view(db)
    db.commit()
    return view


@router.delete("/list/staples/{staple_id}", response_model=StapleView)
def remove_from_trip(staple_id: int, db: Session = Depends(get_db)):
    service.remove_from_trip(db, staple_id)
    view = service.get_view(db)
    db.commit()
    return view
```

- [ ] **Step 4: Register in `backend/app/main.py`** — add near the other router imports:
```python
from app.staples.router import router as staples_router
```
and after `app.include_router(pantry_router)`:
```python
app.include_router(staples_router)
```

- [ ] **Step 5: Run staples router tests + FULL backend suite (backend completion checkpoint):**
```bash
uv run pytest tests/test_staples_router.py -v
uv run pytest -q
```
Report the total. Both green.

- [ ] **Step 6: Commit:**
```bash
git add app/staples/router.py app/main.py tests/test_staples_router.py
git commit -m "feat(staples): catalog + on-trip endpoints"
```

---

## Task B5: Frontend — staples API + types

**Files:**
- Modify: `frontend/src/recipes/types.ts`, `frontend/src/api.ts`
- Test: `frontend/src/recipes/staplesApi.test.ts`

- [ ] **Step 1: Write failing test** `frontend/src/recipes/staplesApi.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addStaple, addStapleToTrip, getStaples, removeStaple, removeStapleFromTrip, setStapleAutoAdd,
} from "../api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response);
}

describe("staples api", () => {
  it("getStaples GETs /list/staples", async () => {
    const f = mockFetch({ staples: [] });
    await getStaples();
    expect(f.mock.calls[0][0]).toContain("/list/staples");
  });
  it("addStaple POSTs /staples with name", async () => {
    const f = mockFetch({ staples: [] });
    await addStaple("peanut butter");
    expect(f.mock.calls[0][0]).toContain("/staples");
    expect(JSON.parse((f.mock.calls[0][1]?.body as string) ?? "{}").name).toBe("peanut butter");
  });
  it("setStapleAutoAdd PATCHes", async () => {
    const f = mockFetch({ staples: [] });
    await setStapleAutoAdd(3, false);
    expect(f.mock.calls[0][1]?.method).toBe("PATCH");
    expect(f.mock.calls[0][0]).toContain("/staples/3");
  });
  it("addStapleToTrip POSTs /list/staples/{id}", async () => {
    const f = mockFetch({ staples: [] });
    await addStapleToTrip(3);
    expect(f.mock.calls[0][0]).toContain("/list/staples/3");
    expect(f.mock.calls[0][1]?.method).toBe("POST");
  });
  it("removeStapleFromTrip DELETEs /list/staples/{id}", async () => {
    const f = mockFetch({ staples: [] });
    await removeStapleFromTrip(3);
    expect(f.mock.calls[0][1]?.method).toBe("DELETE");
  });
  it("removeStaple DELETEs /staples/{id}", async () => {
    const f = mockFetch({ staples: [] });
    await removeStaple(3);
    expect(f.mock.calls[0][0]).toContain("/staples/3");
    expect(f.mock.calls[0][1]?.method).toBe("DELETE");
  });
});
```

- [ ] **Step 2: Run, confirm FAIL:** `npm test -- staplesApi`

- [ ] **Step 3: Add types** — append to `frontend/src/recipes/types.ts`:
```ts
export interface StapleItem {
  id: number;
  ingredient_id: number;
  ingredient_name: string | null;
  auto_add: boolean;
  on_trip: boolean;
}

export interface StapleView {
  staples: StapleItem[];
}
```

- [ ] **Step 4: Add API functions** — in `frontend/src/api.ts`, add `StapleView` to the `./recipes/types` import, then append:
```ts
export async function getStaples(): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/list/staples`));
}

export async function addStaple(name: string): Promise<StapleView> {
  const res = await fetch(`${BASE_URL}/staples`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return json<StapleView>(res);
}

export async function removeStaple(id: number): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/staples/${id}`, { method: "DELETE" }));
}

export async function setStapleAutoAdd(id: number, autoAdd: boolean): Promise<StapleView> {
  const res = await fetch(`${BASE_URL}/staples/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auto_add: autoAdd }),
  });
  return json<StapleView>(res);
}

export async function addStapleToTrip(id: number): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/list/staples/${id}`, { method: "POST" }));
}

export async function removeStapleFromTrip(id: number): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/list/staples/${id}`, { method: "DELETE" }));
}
```

- [ ] **Step 5: Run, confirm PASS + build:** `npm test -- staplesApi` then `npm run build`.

- [ ] **Step 6: Commit:**
```bash
git add src/recipes/types.ts src/api.ts src/recipes/staplesApi.test.ts
git commit -m "feat(web): staples api client + types"
```

---

## Task B6: Frontend — Staples section + embed in GroceryList

**Files:**
- Create: `frontend/src/recipes/StaplesSection.tsx`, `frontend/src/recipes/StaplesSection.test.tsx`
- Modify: `frontend/src/recipes/GroceryList.tsx`

- [ ] **Step 1: Write failing test** `frontend/src/recipes/StaplesSection.test.tsx`:
```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { StaplesSection } from "./StaplesSection";

afterEach(() => vi.restoreAllMocks());

const view = {
  staples: [
    { id: 1, ingredient_id: 2, ingredient_name: "peanut butter", auto_add: true, on_trip: true },
    { id: 2, ingredient_id: 3, ingredient_name: "rice", auto_add: false, on_trip: false },
  ],
};

describe("StaplesSection", () => {
  it("lists staples with on-trip state", async () => {
    vi.spyOn(api, "getStaples").mockResolvedValue(view);
    render(<StaplesSection onChange={() => {}} />);
    expect(await screen.findByText(/peanut butter/)).toBeInTheDocument();
    expect(screen.getByText(/rice/)).toBeInTheDocument();
  });

  it("adds a staple by name", async () => {
    vi.spyOn(api, "getStaples").mockResolvedValue(view);
    const add = vi.spyOn(api, "addStaple").mockResolvedValue(view);
    render(<StaplesSection onChange={() => {}} />);
    fireEvent.change(await screen.findByLabelText(/add a staple/i), { target: { value: "butter" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));
    await waitFor(() => expect(add).toHaveBeenCalledWith("butter"));
  });

  it("toggling a not-on-trip staple adds it to the trip", async () => {
    vi.spyOn(api, "getStaples").mockResolvedValue(view);
    const addTrip = vi.spyOn(api, "addStapleToTrip").mockResolvedValue(view);
    const onChange = vi.fn();
    render(<StaplesSection onChange={onChange} />);
    // rice (id 2) is not on the trip; its checkbox is unchecked → clicking adds it.
    const riceToggle = await screen.findByLabelText(/include rice/i);
    fireEvent.click(riceToggle);
    await waitFor(() => expect(addTrip).toHaveBeenCalledWith(2));
    expect(onChange).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run, confirm FAIL:** `npm test -- StaplesSection`

- [ ] **Step 3: Create `frontend/src/recipes/StaplesSection.tsx`:**
```tsx
import { useEffect, useState } from "react";

import {
  addStaple, addStapleToTrip, getStaples, removeStaple, removeStapleFromTrip, setStapleAutoAdd,
} from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import type { StapleView } from "./types";

export function StaplesSection({ onChange }: { onChange: () => void }) {
  const [view, setView] = useState<StapleView | null>(null);
  const [name, setName] = useState("");

  useEffect(() => {
    getStaples().then(setView).catch(() => setView(null));
  }, []);

  // Every staples mutation refreshes both this section and the parent grocery list.
  function apply(next: StapleView) {
    setView(next);
    onChange();
  }

  async function add() {
    if (!name.trim()) return;
    apply(await addStaple(name.trim()));
    setName("");
  }

  async function toggleTrip(id: number, onTrip: boolean) {
    apply(onTrip ? await removeStapleFromTrip(id) : await addStapleToTrip(id));
  }

  async function toggleAuto(id: number, autoAdd: boolean) {
    setView(await setStapleAutoAdd(id, autoAdd));
  }

  async function remove(id: number) {
    apply(await removeStaple(id));
  }

  if (!view) return null;

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Staples</h3>
      <ul className="flex flex-col gap-1">
        {view.staples.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                aria-label={`Include ${s.ingredient_name}`}
                checked={s.on_trip}
                onChange={() => toggleTrip(s.id, s.on_trip)}
              />
              <span className="text-heading">{s.ingredient_name}</span>
            </label>
            <label className="ml-auto flex items-center gap-1 text-xs text-muted">
              <input
                type="checkbox"
                aria-label={`Auto-add ${s.ingredient_name}`}
                checked={s.auto_add}
                onChange={() => toggleAuto(s.id, !s.auto_add)}
              />
              auto-add
            </label>
            <Button variant="link" onClick={() => remove(s.id)}>remove</Button>
          </li>
        ))}
      </ul>
      <div className="flex items-end gap-2">
        <Input label="Add a staple" value={name} onChange={(e) => setName(e.target.value)} className="w-48" />
        <Button variant="secondary" onClick={add}>Add</Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Run, confirm PASS:** `npm test -- StaplesSection`

- [ ] **Step 5: Embed in `frontend/src/recipes/GroceryList.tsx`.** Add the import next to the others:
```tsx
import { StaplesSection } from "./StaplesSection";
```
The grocery list refetches when staples change, so add a refetch helper and render the section. Replace the `useEffect`/loader area and the JSX so there's a reusable `load()` and `<StaplesSection>` is rendered after the Shopping list card and before `<PantryCheck />`:

Change the effect to a named loader:
```tsx
  const [list, setList] = useState<GroceryListData | null>(null);

  function load() {
    getList().then(setList).catch(() => setList(null));
  }

  useEffect(() => {
    load();
  }, []);
```
Then in the JSX (non-empty branch), after the "Shopping list" `</Card>` and before `<PantryCheck />`, add:
```tsx
          <StaplesSection onChange={load} />
```

- [ ] **Step 6: Update `frontend/src/recipes/GroceryList.test.tsx`** so the embedded StaplesSection's `getStaples` call is mocked — add to the `beforeEach`:
```tsx
  vi.spyOn(api, "getStaples").mockResolvedValue({ staples: [] });
```

- [ ] **Step 7: Run affected suites + build:** `npm test -- recipes/StaplesSection recipes/GroceryList` then `npm run build`.

- [ ] **Step 8: Commit:**
```bash
git add src/recipes/StaplesSection.tsx src/recipes/StaplesSection.test.tsx src/recipes/GroceryList.tsx src/recipes/GroceryList.test.tsx
git commit -m "feat(web): Staples section on the grocery list"
```

---

## Task B7: Final verification

- [ ] **Step 1: Full backend suite (isolated DB)**
```bash
cd backend
export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test
uv run pytest -q
```
Expected: all pass. Report the count.

- [ ] **Step 2: Migrations apply base→head cleanly** (the test DB is managed by conftest, so verify on a reset schema):
```bash
docker exec bushel-test-pg psql -U bushel -d bushel_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
uv run alembic upgrade head
docker exec bushel-test-pg psql -U bushel -d bushel_test -c "\dt" | grep -E "app_settings|staples"
```
Expected: chain runs through `f6a7b8c9d0e1`; `app_settings`, `staples`, `grocery_list_staples` present.

- [ ] **Step 3: Full frontend suite + build**
```bash
cd ../frontend
npm test
npm run build
```
Expected: all pass; build clean.

- [ ] **Step 4: app imports**
```bash
cd ../backend && uv run python -c "from app.main import app; print('app ok')"
```

- [ ] **Step 5: Commit any cleanup** (allow-empty):
```bash
git commit --allow-empty -m "chore: home-store + staples final verification"
```

---

## Done criteria

- `uv run pytest -q` and `npm test` + `npm run build` all green; migrations apply base→head.
- Home store persists across drafts/refreshes and shows by name; no re-pick after sending a list.
- Saved staples: add by name, auto-add toggle, per-trip include/remove; auto staples seed once per draft and flow into the list (consolidation/silent-reuse/pantry); UPC remembered per ingredient.
- Merged to `master` via finishing-a-development-branch.

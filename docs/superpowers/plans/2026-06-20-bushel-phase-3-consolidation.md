# Bushel Phase 3 — Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the consolidation subsystem — assemble one active draft grocery list by adding recipes (with per-recipe target servings), scale and merge their ingredients across recipes, sum quantities with `pint` (keeping incompatible units as separate sub-quantities), and expose it through a draft-list API and a new React Grocery List screen.

**Architecture:** Builds on completed Phase 1+2 (FastAPI + Postgres + React; recipes with parsed `qty`/`unit` + canonical ingredients exist). Two additive migrations: a `grocery_list_recipes` membership table and a `quantities` JSONB column on `grocery_list_items`. A new `app/consolidate/` package: a **pure, `pint`-wrapped `units.py` core** (the only file importing `pint`), a delete-and-rebuild `service.py` (owns the single draft-list and all writes), `schemas.py`, and a thin `router.py`. No LLM anywhere in this phase — consolidation is deterministic math. `purchase_qty`/packages are deferred to Phase 4.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / uv; `pint` (made an explicit dependency); React 18 / TypeScript / Vite / Vitest.

---

## Important context for the implementer

- **Existing models** (`backend/app/models.py`): `GroceryList` (id, name, status default "draft", store_location_id, created_at, sent_at); `GroceryListItem` (id, list_id→grocery_lists CASCADE, ingredient_id→ingredients CASCADE, total_qty Float nullable, total_unit String(50) nullable, purchase_qty Integer default 1, kroger_upc, source_recipe_ids ARRAY(Integer) default list, pantry_status String(20) default "needed"); `Recipe` (id, title, default_servings, source_url, created_at); `RecipeIngredient` (recipe_id, raw_text, qty Float nullable, unit String(50) nullable, ingredient_id nullable, parse_source, needs_review); `Ingredient` (id, canonical_name, aliases, category, default_purchase_unit).
- **DB/test conventions:** `db_session` fixture (per-test transaction rolled back) in `backend/tests/conftest.py`; tests need Postgres — `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5432/bushel_test` with `bushel-pg` running. Run `uv run pytest` from `backend/`. Migrations: `uv run alembic ...`. The migration chain head before Phase 3 is `b91365f1a33d` (widen parse_source).
- **`pint` is the only version-sensitive piece.** Task 4 has an explicit step to verify the installed `pint` API before writing `units.py`, and `pint` is imported ONLY in `units.py`.
- **No LLM** in Phase 3 — nothing to mock for the LLM.

## File Structure

```
backend/
├── pyproject.toml                       # + pint (explicit)
├── migrations/versions/<rev>_*.py       # 2 new migrations
├── app/
│   ├── main.py                          # MODIFY: include consolidate router
│   ├── models.py                        # MODIFY: + GroceryListRecipe; + quantities col on GroceryListItem
│   └── consolidate/
│       ├── __init__.py
│       ├── units.py                     # pure pint-wrapped consolidation (only pint importer)
│       ├── schemas.py                   # Pydantic request/response models
│       ├── service.py                   # draft-list singleton + delete-and-rebuild (only writer)
│       └── router.py                    # GET /list, POST/PATCH/DELETE /list/recipes
└── tests/
    ├── test_units.py
    ├── test_consolidate_service.py
    └── test_consolidate_router.py
frontend/src/
├── api.ts                               # MODIFY: + list endpoints
├── App.tsx                              # MODIFY: + "Grocery List" nav/view
└── recipes/
    ├── types.ts                         # MODIFY: + list types
    ├── GroceryList.tsx                  # new screen
    ├── GroceryList.test.tsx
    ├── RecipeList.tsx                   # MODIFY: + "Add to list" action
    └── RecipeList.test.tsx              # MODIFY: cover add-to-list
```

---

## Task 1: Make `pint` an explicit dependency

**Files:** Modify `backend/pyproject.toml`

- [ ] **Step 1: Add `pint` to `[project].dependencies`** in `backend/pyproject.toml` (keep all existing entries):

```
    "pint>=0.23",
```

- [ ] **Step 2: Resolve and verify**

Run (from `backend/`): `uv lock && uv sync`
Then: `uv run python -c "import pint; print(pint.__version__)"`
Expected: prints a version (≥0.23).

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "build(backend): make pint an explicit dependency"
```

---

## Task 2: `grocery_list_recipes` model + migration

**Files:** Modify `backend/app/models.py`; Test `backend/tests/test_models.py` (append); Create a migration.

- [ ] **Step 1: Append the failing test** to `backend/tests/test_models.py`:

```python
def test_grocery_list_recipe_model():
    from app.models import GroceryListRecipe

    cols = GroceryListRecipe.__table__.columns
    assert GroceryListRecipe.__tablename__ == "grocery_list_recipes"
    assert {"id", "list_id", "recipe_id", "servings"} <= set(cols.keys())
    # unique (list_id, recipe_id)
    uniques = [c for c in GroceryListRecipe.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert any({col.name for col in u.columns} == {"list_id", "recipe_id"} for u in uniques)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_models.py::test_grocery_list_recipe_model -v`
Expected: FAIL — `GroceryListRecipe` does not exist.

- [ ] **Step 3: Add the model** to `backend/app/models.py`. `UniqueConstraint` must be imported from `sqlalchemy` (add it to the existing `from sqlalchemy import (...)` block). Append the class:

```python
class GroceryListRecipe(Base):
    __tablename__ = "grocery_list_recipes"
    __table_args__ = (UniqueConstraint("list_id", "recipe_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"))
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    servings: Mapped[int] = mapped_column(Integer)
```

- [ ] **Step 4: Run the model test to verify it passes**

Run: `uv run pytest tests/test_models.py::test_grocery_list_recipe_model -v`
Expected: PASS.

- [ ] **Step 5: Generate the migration**

Ensure `DATABASE_URL` points at a DB at current head (`uv run alembic upgrade head` first).
Run (from `backend/`): `uv run alembic revision --autogenerate -m "add grocery_list_recipes"`
Open the generated file; confirm `upgrade()` creates the `grocery_list_recipes` table with the two FKs and the unique constraint, and nothing else. If unrelated drift appears, the DB wasn't at head — fix and regenerate.

- [ ] **Step 6: Apply + verify reversibility**

Run: `uv run alembic upgrade head` then `uv run alembic downgrade -1` then `uv run alembic upgrade head`
Expected: all succeed.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py backend/migrations/versions
git commit -m "feat(backend): add grocery_list_recipes membership table"
```

---

## Task 3: `quantities` JSONB column on `grocery_list_items` + migration

**Files:** Modify `backend/app/models.py`; Test `backend/tests/test_models.py` (append); Create a migration.

- [ ] **Step 1: Append the failing test** to `backend/tests/test_models.py`:

```python
def test_grocery_list_item_has_quantities():
    from app.models import GroceryListItem

    assert "quantities" in GroceryListItem.__table__.columns
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_models.py::test_grocery_list_item_has_quantities -v`
Expected: FAIL — no `quantities` column.

- [ ] **Step 3: Add the column** to the existing `GroceryListItem` class in `backend/app/models.py`. Add the import `from sqlalchemy.dialects.postgresql import JSONB` near the existing `from sqlalchemy.dialects.postgresql import ARRAY` import (combine: `from sqlalchemy.dialects.postgresql import ARRAY, JSONB`). Add the column after `source_recipe_ids`:

```python
    quantities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
```

- [ ] **Step 4: Run the model test to verify it passes**

Run: `uv run pytest tests/test_models.py::test_grocery_list_item_has_quantities -v`
Expected: PASS.

- [ ] **Step 5: Generate the migration**

(DB at head.) Run: `uv run alembic revision --autogenerate -m "add quantities to grocery_list_items"`
Confirm `upgrade()` is exactly one `op.add_column("grocery_list_items", sa.Column("quantities", postgresql.JSONB(...), server_default="[]", ...))`. No other drift.

- [ ] **Step 6: Apply + verify reversibility**

Run: `uv run alembic upgrade head` then `uv run alembic downgrade -1` then `uv run alembic upgrade head`
Expected: all succeed.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py backend/migrations/versions
git commit -m "feat(backend): add quantities JSONB column to grocery_list_items"
```

---

## Task 4: `consolidate/units.py` — the pure pint-wrapped core

**Files:** Create `backend/app/consolidate/__init__.py` (empty); Create `backend/app/consolidate/units.py`; Test `backend/tests/test_units.py`.

> **`pint` verification (do FIRST):** Run
> `cd backend && uv run python -c "from pint import UnitRegistry; u=UnitRegistry(); q=2*u('cup'); print(q.to('milliliter')); print(str(q.dimensionality)); 
> from pint import UndefinedUnitError
> try: u('clove')
> except UndefinedUnitError as e: print('clove undefined OK')"`
> Confirm: `cup`→ml conversion works, `.dimensionality` prints a string like `[length] ** 3`, and an unknown unit (`clove`) raises `UndefinedUnitError`. If the import paths differ in the installed version, adjust the imports in `units.py` accordingly (the algorithm is unchanged). Note: `pint` reads bare `t`→tonne and `l`→liter, so cooking aliases (`t`/`T`/`c`/`tbsp`/`tsp`) MUST be normalized to full names BEFORE handing to pint — the `_ALIASES` map below does this.

- [ ] **Step 1: Create the empty package marker** `backend/app/consolidate/__init__.py`.

- [ ] **Step 2: Write the failing test** `backend/tests/test_units.py`:

```python
from app.consolidate.units import consolidate


def _q(items):
    """Helper: call consolidate and return a comparable list of (qty, unit) tuples."""
    return [(r["qty"], r["unit"]) for r in consolidate(items)]


def test_same_unit_sums():
    assert _q([(2.0, "cup"), (1.0, "cup")]) == [(3.0, "cup")]


def test_compatible_units_sum_into_first_seen():
    # 2 cups + 240 ml ≈ 3.014 cups (240 ml ≈ 1.014 cups)
    result = consolidate([(2.0, "cup"), (240.0, "milliliter")])
    assert len(result) == 1
    assert result[0]["unit"] == "cup"
    assert abs(result[0]["qty"] - 3.014) < 0.01


def test_mass_units_compatible():
    # 100 g + 1 oz ≈ 128.35 g
    result = consolidate([(100.0, "gram"), (1.0, "ounce")])
    assert len(result) == 1
    assert result[0]["unit"] == "gram"
    assert abs(result[0]["qty"] - 128.35) < 0.5


def test_incompatible_units_kept_separate():
    result = _q([(2.0, "clove"), (1.0, "tablespoon")])
    assert (2.0, "clove") in result
    assert (1.0, "tablespoon") in result
    assert len(result) == 2


def test_count_items_no_unit():
    assert _q([(2.0, None), (1.0, None)]) == [(3.0, None)]


def test_aliases_normalized_before_pint():
    # tbsp and T both → tablespoon; c → cup; t → teaspoon (NOT tonne)
    assert _q([(1.0, "tbsp"), (1.0, "T")]) == [(2.0, "tablespoon")]
    assert _q([(1.0, "c")]) == [(1.0, "cup")]
    assert _q([(2.0, "t")]) == [(2.0, "teaspoon")]


def test_none_qty_carried_through():
    result = consolidate([(None, "pinch")])
    assert result == [{"qty": None, "unit": "pinch"}]


def test_rounding():
    result = consolidate([(1.0, "cup"), (1.0, "cup"), (0.0001, "cup")])
    assert result[0]["qty"] == 2.0


def test_empty_input():
    assert consolidate([]) == []
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_units.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement** `backend/app/consolidate/units.py`:

```python
"""Pure consolidation of (qty, unit) pairs for one ingredient. The only pint importer.

Compatible units (by pint dimensionality) sum into the first-seen unit of their group;
units pint can't parse stay in their own group keyed by the unit string; count items
(unit is None) sum together; qty=None is carried through as an "as needed" marker.
"""

from __future__ import annotations

from pint import UndefinedUnitError, UnitRegistry

_ureg = UnitRegistry()

# Cooking aliases normalized BEFORE pint (pint reads bare 't'->tonne, 'l'->liter, etc.).
_ALIASES = {
    "tbsp": "tablespoon",
    "tbs": "tablespoon",
    "tb": "tablespoon",
    "t": "teaspoon",
    "tsp": "teaspoon",
    "c": "cup",
    "g": "gram",
    "kg": "kilogram",
    "ml": "milliliter",
    "l": "liter",
    "oz": "ounce",
    "lb": "pound",
    "lbs": "pound",
    "qt": "quart",
    "pt": "pint",
    "gal": "gallon",
}


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    key = unit.strip().lower()
    if not key:
        return None
    # Singular-ish: strip a trailing plural 's' for matching aliases/pint (e.g. "cups").
    base = key[:-1] if key.endswith("s") and key[:-1] in _ALIASES else key
    return _ALIASES.get(base, _ALIASES.get(key, base if base in _ALIASES else key))


def consolidate(items: list[tuple[float | None, str | None]]) -> list[dict]:
    """Return a list of {"qty": float|None, "unit": str|None} sub-quantities."""
    # Each group: {"unit": display_unit, "qty": running_total or None, "dim": key}
    groups: list[dict] = []

    def find(key) -> dict | None:
        for g in groups:
            if g["key"] == key:
                return g
        return None

    for qty, raw_unit in items:
        unit = _normalize_unit(raw_unit)

        if qty is None:
            key = ("none", unit)
            if find(key) is None:
                groups.append({"key": key, "unit": unit, "qty": None})
            continue

        if unit is None:
            key = ("count",)
            g = find(key)
            if g is None:
                groups.append({"key": key, "unit": None, "qty": qty})
            elif g["qty"] is not None:
                g["qty"] += qty
            continue

        # Try pint for a dimensional group.
        try:
            q = qty * _ureg(unit)
            key = ("dim", str(q.dimensionality))
            g = find(key)
            if g is None:
                groups.append({"key": key, "unit": unit, "qty": qty})
            else:
                converted = q.to(g["unit"]).magnitude
                if g["qty"] is not None:
                    g["qty"] += converted
        except (UndefinedUnitError, Exception):  # noqa: BLE001 — pint raises several types for bad units
            key = ("str", unit)
            g = find(key)
            if g is None:
                groups.append({"key": key, "unit": unit, "qty": qty})
            elif g["qty"] is not None:
                g["qty"] += qty

    return [
        {"qty": round(g["qty"], 3) if g["qty"] is not None else None, "unit": g["unit"]}
        for g in groups
    ]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_units.py -v`
Expected: all 9 PASS. If a compatible-units assertion is off, double-check pint's conversion factors with `uv run python -c "from pint import UnitRegistry; u=UnitRegistry(); print((240*u('milliliter')).to('cup'))"` and adjust the test's expected value to the real factor (the algorithm is correct; only the numeric expectation may need the real conversion constant).

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/consolidate/__init__.py backend/app/consolidate/units.py backend/tests/test_units.py
git commit -m "feat(backend): add pure pint-wrapped unit consolidation core"
```

---

## Task 5: `consolidate/schemas.py`

**Files:** Create `backend/app/consolidate/schemas.py`; Test `backend/tests/test_consolidate_schemas.py`.

- [ ] **Step 1: Write the failing test** `backend/tests/test_consolidate_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.consolidate.schemas import AddRecipeRequest, SetServingsRequest


def test_add_recipe_request_servings_optional():
    assert AddRecipeRequest(recipe_id=5).servings is None
    assert AddRecipeRequest(recipe_id=5, servings=8).servings == 8


def test_set_servings_requires_servings():
    assert SetServingsRequest(servings=4).servings == 4
    with pytest.raises(ValidationError):
        SetServingsRequest()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_consolidate_schemas.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `backend/app/consolidate/schemas.py`:

```python
"""Pydantic request/response models for the consolidation (grocery list) API."""

from __future__ import annotations

from pydantic import BaseModel


class AddRecipeRequest(BaseModel):
    recipe_id: int
    servings: int | None = None


class SetServingsRequest(BaseModel):
    servings: int


class SubQuantity(BaseModel):
    qty: float | None
    unit: str | None


class ListItemRead(BaseModel):
    ingredient_id: int
    ingredient_name: str | None
    category: str | None
    quantities: list[SubQuantity]
    source_recipe_ids: list[int]
    pantry_status: str


class ListRecipeRead(BaseModel):
    recipe_id: int
    title: str
    servings: int
    default_servings: int


class ListRead(BaseModel):
    id: int
    status: str
    recipes: list[ListRecipeRead]
    items: list[ListItemRead]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_consolidate_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/consolidate/schemas.py backend/tests/test_consolidate_schemas.py
git commit -m "feat(backend): add consolidation API schemas"
```

---

## Task 6: `consolidate/service.py` — draft singleton + delete-and-rebuild

**Files:** Create `backend/app/consolidate/service.py`; Test `backend/tests/test_consolidate_service.py`.

- [ ] **Step 1: Write the failing test** `backend/tests/test_consolidate_service.py`:

```python
import pytest

from app.consolidate.service import (
    NotOnListError,
    add_recipe,
    get_or_create_draft,
    remove_recipe,
    set_servings,
)
from app.models import GroceryList, GroceryListItem, GroceryListRecipe, Ingredient, Recipe, RecipeIngredient


def _recipe(db, title, default_servings, lines):
    """lines = [(qty, unit, ingredient)]; ingredient is an Ingredient row."""
    r = Recipe(title=title, default_servings=default_servings)
    db.add(r)
    db.flush()
    for qty, unit, ing in lines:
        db.add(RecipeIngredient(
            recipe_id=r.id, raw_text=f"{qty} {unit} {ing.canonical_name}", qty=qty, unit=unit,
            ingredient_id=ing.id, parse_source="library", needs_review=False,
        ))
    db.flush()
    return r


def test_get_or_create_draft_is_singleton(db_session):
    a = get_or_create_draft(db_session)
    b = get_or_create_draft(db_session)
    assert a.id == b.id
    assert a.status == "draft"


def test_add_recipe_scales_and_consolidates(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    egg = Ingredient(canonical_name="egg", aliases=[])
    db_session.add_all([flour, egg])
    db_session.flush()
    pancakes = _recipe(db_session, "Pancakes", 4, [(2.0, "cup", flour), (2.0, None, egg)])
    bread = _recipe(db_session, "Bread", 2, [(1.0, "cup", flour)])

    add_recipe(db_session, pancakes.id, servings=6)   # factor 1.5 → 3 cups flour, 3 eggs
    draft = add_recipe(db_session, bread.id, servings=2)  # factor 1.0 → +1 cup flour

    items = db_session.query(GroceryListItem).filter_by(list_id=draft.id).all()
    by_ing = {i.ingredient_id: i for i in items}
    # flour: 3 cups (from pancakes) + 1 cup (bread) = 4 cups
    flour_item = by_ing[flour.id]
    assert flour_item.quantities == [{"qty": 4.0, "unit": "cup"}]
    assert flour_item.total_qty == 4.0 and flour_item.total_unit == "cup"
    assert sorted(flour_item.source_recipe_ids) == sorted([pancakes.id, bread.id])
    # eggs: 3
    assert by_ing[egg.id].quantities == [{"qty": 3.0, "unit": None}]


def test_add_recipe_upserts_servings(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 2, [(1.0, "cup", flour)])

    add_recipe(db_session, r.id, servings=2)
    add_recipe(db_session, r.id, servings=4)  # upsert, not duplicate

    memberships = db_session.query(GroceryListRecipe).filter_by(recipe_id=r.id).all()
    assert len(memberships) == 1
    assert memberships[0].servings == 4
    # factor 2.0 → 2 cups
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert item.quantities == [{"qty": 2.0, "unit": "cup"}]


def test_rebuild_is_idempotent(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 1, [(1.0, "cup", flour)])
    add_recipe(db_session, r.id, servings=1)
    first = db_session.query(GroceryListItem).count()
    set_servings(db_session, r.id, 1)  # recompute, same inputs
    assert db_session.query(GroceryListItem).count() == first


def test_remove_recipe(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 1, [(1.0, "cup", flour)])
    add_recipe(db_session, r.id, servings=1)
    draft = remove_recipe(db_session, r.id)
    assert db_session.query(GroceryListItem).filter_by(list_id=draft.id).count() == 0


def test_set_servings_missing_recipe_raises(db_session):
    get_or_create_draft(db_session)
    with pytest.raises(NotOnListError):
        set_servings(db_session, 9999, 4)


def test_zero_default_servings_does_not_divide_by_zero(db_session):
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    db_session.flush()
    r = _recipe(db_session, "R", 0, [(1.0, "cup", flour)])  # default_servings 0
    add_recipe(db_session, r.id, servings=3)  # factor guarded → treat default as 1 → 3 cups
    item = db_session.query(GroceryListItem).filter_by(ingredient_id=flour.id).one()
    assert item.quantities == [{"qty": 3.0, "unit": "cup"}]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_consolidate_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `backend/app/consolidate/service.py`:

```python
"""Draft grocery list management + delete-and-rebuild consolidation.

The only writer of grocery_list_recipes and grocery_list_items.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.consolidate.units import consolidate
from app.models import (
    GroceryList,
    GroceryListItem,
    GroceryListRecipe,
    Ingredient,
    Recipe,
    RecipeIngredient,
)


class NotOnListError(Exception):
    """Raised when a recipe targeted by patch/remove is not on the draft list."""


def get_or_create_draft(db: Session) -> GroceryList:
    draft = db.execute(
        select(GroceryList).where(GroceryList.status == "draft").order_by(GroceryList.id.desc())
    ).scalars().first()
    if draft is None:
        draft = GroceryList(name="Draft", status="draft")
        db.add(draft)
        db.flush()
    return draft


def _membership(db: Session, list_id: int, recipe_id: int) -> GroceryListRecipe | None:
    return db.execute(
        select(GroceryListRecipe).where(
            GroceryListRecipe.list_id == list_id, GroceryListRecipe.recipe_id == recipe_id
        )
    ).scalars().first()


def _recompute(db: Session, draft: GroceryList) -> None:
    """Delete the list's items and rebuild them from its recipe memberships."""
    db.execute(delete(GroceryListItem).where(GroceryListItem.list_id == draft.id))

    memberships = db.execute(
        select(GroceryListRecipe).where(GroceryListRecipe.list_id == draft.id)
    ).scalars().all()

    # ingredient_id -> {"quantities": [(qty, unit), ...], "recipes": set[int]}
    grouped: dict[int, dict] = defaultdict(lambda: {"quantities": [], "recipes": set()})

    for m in memberships:
        recipe = db.get(Recipe, m.recipe_id)
        default = recipe.default_servings or 1
        factor = m.servings / default
        rows = db.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == m.recipe_id,
                RecipeIngredient.ingredient_id.is_not(None),
            )
        ).scalars().all()
        for row in rows:
            scaled = row.qty * factor if row.qty is not None else None
            grouped[row.ingredient_id]["quantities"].append((scaled, row.unit))
            grouped[row.ingredient_id]["recipes"].add(m.recipe_id)

    for ingredient_id, data in grouped.items():
        quantities = consolidate(data["quantities"])
        single = quantities[0] if len(quantities) == 1 else None
        db.add(
            GroceryListItem(
                list_id=draft.id,
                ingredient_id=ingredient_id,
                quantities=quantities,
                total_qty=single["qty"] if single else None,
                total_unit=single["unit"] if single else None,
                source_recipe_ids=sorted(data["recipes"]),
                pantry_status="needed",
            )
        )
    db.flush()


def add_recipe(db: Session, recipe_id: int, servings: int | None = None) -> GroceryList:
    draft = get_or_create_draft(db)
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise NotOnListError(f"recipe {recipe_id} does not exist")
    target = servings if servings is not None else (recipe.default_servings or 1)
    existing = _membership(db, draft.id, recipe_id)
    if existing is not None:
        existing.servings = target
    else:
        db.add(GroceryListRecipe(list_id=draft.id, recipe_id=recipe_id, servings=target))
    db.flush()
    _recompute(db, draft)
    return draft


def set_servings(db: Session, recipe_id: int, servings: int) -> GroceryList:
    draft = get_or_create_draft(db)
    existing = _membership(db, draft.id, recipe_id)
    if existing is None:
        raise NotOnListError(f"recipe {recipe_id} not on list")
    existing.servings = servings
    db.flush()
    _recompute(db, draft)
    return draft


def remove_recipe(db: Session, recipe_id: int) -> GroceryList:
    draft = get_or_create_draft(db)
    existing = _membership(db, draft.id, recipe_id)
    if existing is None:
        raise NotOnListError(f"recipe {recipe_id} not on list")
    db.delete(existing)
    db.flush()
    _recompute(db, draft)
    return draft
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_consolidate_service.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/consolidate/service.py backend/tests/test_consolidate_service.py
git commit -m "feat(backend): add draft-list consolidation service"
```

---

## Task 7: `consolidate/router.py` + register in `main.py`

**Files:** Create `backend/app/consolidate/router.py`; Modify `backend/app/main.py`; Test `backend/tests/test_consolidate_router.py`.

- [ ] **Step 1: Write the failing test** `backend/tests/test_consolidate_router.py`:

```python
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Ingredient, Recipe, RecipeIngredient


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed_recipe(db_session, title="R", default_servings=2):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db_session.add(ing)
    db_session.flush()
    r = Recipe(title=title, default_servings=default_servings)
    db_session.add(r)
    db_session.flush()
    db_session.add(RecipeIngredient(
        recipe_id=r.id, raw_text="1 cup flour", qty=1.0, unit="cup",
        ingredient_id=ing.id, parse_source="library", needs_review=False,
    ))
    db_session.flush()
    return r, ing


def test_get_list_creates_empty_draft(db_session):
    client = _client(db_session)
    resp = client.get("/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "draft"
    assert body["recipes"] == []
    assert body["items"] == []
    app.dependency_overrides.clear()


def test_add_recipe_returns_consolidated_list(db_session):
    r, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.post("/list/recipes", json={"recipe_id": r.id, "servings": 4})
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipes"][0]["recipe_id"] == r.id
    assert body["recipes"][0]["servings"] == 4
    item = body["items"][0]
    assert item["ingredient_name"] == "flour"
    assert item["category"] == "baking"
    assert item["quantities"] == [{"qty": 2.0, "unit": "cup"}]  # 1 cup * (4/2)
    app.dependency_overrides.clear()


def test_patch_servings(db_session):
    r, ing = _seed_recipe(db_session)
    client = _client(db_session)
    client.post("/list/recipes", json={"recipe_id": r.id})
    resp = client.patch(f"/list/recipes/{r.id}", json={"servings": 6})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["quantities"] == [{"qty": 3.0, "unit": "cup"}]  # 1 * (6/2)
    app.dependency_overrides.clear()


def test_patch_missing_recipe_404(db_session):
    client = _client(db_session)
    client.get("/list")
    resp = client.patch("/list/recipes/9999", json={"servings": 4})
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_delete_recipe(db_session):
    r, ing = _seed_recipe(db_session)
    client = _client(db_session)
    client.post("/list/recipes", json={"recipe_id": r.id})
    resp = client.delete(f"/list/recipes/{r.id}")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_consolidate_router.py -v`
Expected: FAIL — routes 404 / module not found.

- [ ] **Step 3: Implement** `backend/app/consolidate/router.py`:

```python
"""HTTP layer for the draft grocery list. Thin — delegates to the service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consolidate.schemas import (
    AddRecipeRequest,
    ListItemRead,
    ListRead,
    ListRecipeRead,
    SetServingsRequest,
    SubQuantity,
)
from app.consolidate.service import (
    NotOnListError,
    add_recipe,
    get_or_create_draft,
    remove_recipe,
    set_servings,
)
from app.db import get_db
from app.models import (
    GroceryList,
    GroceryListItem,
    GroceryListRecipe,
    Ingredient,
    Recipe,
)

router = APIRouter(prefix="/list", tags=["list"])

# Coarse shopping order; unknown/None categories sort last.
_CATEGORY_ORDER = [
    "produce", "meat", "dairy", "baking", "pantry", "frozen", "beverage", "spice", "other",
]


def _serialize(draft: GroceryList, db: Session) -> ListRead:
    memberships = db.execute(
        select(GroceryListRecipe).where(GroceryListRecipe.list_id == draft.id)
    ).scalars().all()
    recipe_by_id = {r.id: r for r in db.execute(select(Recipe)).scalars().all()}
    recipes = [
        ListRecipeRead(
            recipe_id=m.recipe_id,
            title=recipe_by_id[m.recipe_id].title,
            servings=m.servings,
            default_servings=recipe_by_id[m.recipe_id].default_servings,
        )
        for m in memberships
    ]

    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    rows = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
    ).scalars().all()

    def cat_key(item: GroceryListItem):
        cat = ing_by_id[item.ingredient_id].category
        order = _CATEGORY_ORDER.index(cat) if cat in _CATEGORY_ORDER else len(_CATEGORY_ORDER)
        return (order, ing_by_id[item.ingredient_id].canonical_name)

    items = [
        ListItemRead(
            ingredient_id=r.ingredient_id,
            ingredient_name=ing_by_id[r.ingredient_id].canonical_name,
            category=ing_by_id[r.ingredient_id].category,
            quantities=[SubQuantity(**q) for q in r.quantities],
            source_recipe_ids=r.source_recipe_ids,
            pantry_status=r.pantry_status,
        )
        for r in sorted(rows, key=cat_key)
    ]
    return ListRead(id=draft.id, status=draft.status, recipes=recipes, items=items)


@router.get("", response_model=ListRead)
def get_list(db: Session = Depends(get_db)):
    draft = get_or_create_draft(db)
    db.commit()
    return _serialize(draft, db)


@router.post("/recipes", response_model=ListRead)
def add_recipe_endpoint(body: AddRecipeRequest, db: Session = Depends(get_db)):
    try:
        draft = add_recipe(db, body.recipe_id, body.servings)
    except NotOnListError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(draft, db)


@router.patch("/recipes/{recipe_id}", response_model=ListRead)
def set_servings_endpoint(recipe_id: int, body: SetServingsRequest, db: Session = Depends(get_db)):
    try:
        draft = set_servings(db, recipe_id, body.servings)
    except NotOnListError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(draft, db)


@router.delete("/recipes/{recipe_id}", response_model=ListRead)
def remove_recipe_endpoint(recipe_id: int, db: Session = Depends(get_db)):
    try:
        draft = remove_recipe(db, recipe_id)
    except NotOnListError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(draft, db)
```

- [ ] **Step 4: Register the router** in `backend/app/main.py`. Add the import and the `include_router` call (keep the existing health route and recipes router):

```python
from app.consolidate.router import router as list_router
```
and after the existing `app.include_router(recipes_router)` line:
```python
app.include_router(list_router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_consolidate_router.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the FULL backend suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/consolidate/router.py backend/app/main.py backend/tests/test_consolidate_router.py
git commit -m "feat(backend): add draft grocery list API router"
```

---

## Task 8: Frontend list API client + types

**Files:** Modify `frontend/src/recipes/types.ts`; Modify `frontend/src/api.ts`; Test `frontend/src/recipes/listApi.test.ts`.

- [ ] **Step 1: Append list types** to `frontend/src/recipes/types.ts`:

```typescript
export interface SubQuantity {
  qty: number | null;
  unit: string | null;
}

export interface ListItem {
  ingredient_id: number;
  ingredient_name: string | null;
  category: string | null;
  quantities: SubQuantity[];
  source_recipe_ids: number[];
  pantry_status: string;
}

export interface ListRecipe {
  recipe_id: number;
  title: string;
  servings: number;
  default_servings: number;
}

export interface GroceryListData {
  id: number;
  status: string;
  recipes: ListRecipe[];
  items: ListItem[];
}
```

- [ ] **Step 2: Write the failing test** `frontend/src/recipes/listApi.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { addRecipeToList, getList, removeRecipeFromList, updateListServings } from "../api";

afterEach(() => vi.restoreAllMocks());

const listJson = { id: 1, status: "draft", recipes: [], items: [] };

describe("list api", () => {
  it("getList GETs /list", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    const list = await getList();
    expect(list.status).toBe("draft");
    expect(spy).toHaveBeenCalledWith(expect.stringContaining("/list"), undefined);
  });

  it("addRecipeToList POSTs recipe_id and servings", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    await addRecipeToList(5, 4);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/list/recipes"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("updateListServings PATCHes", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    await updateListServings(5, 6);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/list/recipes/5"),
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("removeRecipeFromList DELETEs", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    await removeRecipeFromList(5);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/list/recipes/5"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/recipes/listApi.test.ts`
Expected: FAIL — functions not exported.

- [ ] **Step 4: Append to `frontend/src/api.ts`** (keep existing content; add the `GroceryListData` type to the existing `import type ... from "./recipes/types"` line, or add a new import line):

```typescript
import type { GroceryListData } from "./recipes/types";

export async function getList(): Promise<GroceryListData> {
  return json<GroceryListData>(await fetch(`${BASE_URL}/list`));
}

export async function addRecipeToList(
  recipeId: number,
  servings?: number,
): Promise<GroceryListData> {
  const res = await fetch(`${BASE_URL}/list/recipes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recipe_id: recipeId, servings }),
  });
  return json<GroceryListData>(res);
}

export async function updateListServings(
  recipeId: number,
  servings: number,
): Promise<GroceryListData> {
  const res = await fetch(`${BASE_URL}/list/recipes/${recipeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ servings }),
  });
  return json<GroceryListData>(res);
}

export async function removeRecipeFromList(recipeId: number): Promise<GroceryListData> {
  const res = await fetch(`${BASE_URL}/list/recipes/${recipeId}`, { method: "DELETE" });
  return json<GroceryListData>(res);
}
```

(The `json<T>` helper already exists in api.ts from Phase 2.)

- [ ] **Step 5: Run the test to verify it passes**

Run (from `frontend/`): `npm test -- src/recipes/listApi.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Full frontend suite + build**

Run: `npm test` then `npm run build`
Expected: all pass; clean build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/recipes/types.ts frontend/src/api.ts frontend/src/recipes/listApi.test.ts
git commit -m "feat(frontend): add grocery list API client + types"
```

---

## Task 9: `GroceryList` screen

**Files:** Create `frontend/src/recipes/GroceryList.tsx`; Test `frontend/src/recipes/GroceryList.test.tsx`.

- [ ] **Step 1: Write the failing test** `frontend/src/recipes/GroceryList.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GroceryList } from "./GroceryList";

afterEach(() => vi.restoreAllMocks());

const emptyList = { id: 1, status: "draft", recipes: [], items: [] };

const populatedList = {
  id: 1,
  status: "draft",
  recipes: [{ recipe_id: 5, title: "Pancakes", servings: 6, default_servings: 4 }],
  items: [
    {
      ingredient_id: 10, ingredient_name: "garlic", category: "produce",
      quantities: [{ qty: 3, unit: "clove" }, { qty: 1, unit: "tbsp" }],
      source_recipe_ids: [5], pantry_status: "needed",
    },
    {
      ingredient_id: 11, ingredient_name: "flour", category: "baking",
      quantities: [{ qty: 4, unit: "cup" }], source_recipe_ids: [5], pantry_status: "needed",
    },
  ],
};

describe("GroceryList", () => {
  it("shows an empty state when no recipes", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(emptyList), { status: 200 }),
    );
    render(<GroceryList />);
    expect(await screen.findByText(/no recipes on your list/i)).toBeInTheDocument();
  });

  it("renders member recipes and consolidated items with multi-unit quantities", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(populatedList), { status: 200 }),
    );
    render(<GroceryList />);
    expect(await screen.findByText(/pancakes/i)).toBeInTheDocument();
    // multi-unit garlic renders both sub-quantities
    expect(await screen.findByText(/3 clove \+ 1 tbsp/i)).toBeInTheDocument();
    expect(await screen.findByText(/4 cup/i)).toBeInTheDocument();
  });

  it("editing servings calls PATCH and refreshes", async () => {
    const refreshed = {
      ...populatedList,
      recipes: [{ ...populatedList.recipes[0], servings: 8 }],
    };
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(populatedList), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(refreshed), { status: 200 }));

    render(<GroceryList />);
    const input = await screen.findByLabelText(/servings for pancakes/i);
    await userEvent.clear(input);
    await userEvent.type(input, "8");
    await userEvent.click(screen.getByRole("button", { name: /update pancakes/i }));

    await waitFor(() =>
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining("/list/recipes/5"),
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/recipes/GroceryList.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** `frontend/src/recipes/GroceryList.tsx`:

```tsx
import { useEffect, useState } from "react";

import { getList, removeRecipeFromList, updateListServings } from "../api";
import type { GroceryListData, ListRecipe, SubQuantity } from "./types";

function formatQuantities(quantities: SubQuantity[]): string {
  if (quantities.length === 0) return "";
  return quantities
    .map((q) => (q.qty === null ? `as needed${q.unit ? ` (${q.unit})` : ""}` : `${q.qty}${q.unit ? ` ${q.unit}` : ""}`))
    .join(" + ");
}

function RecipeRow({
  recipe,
  onChange,
}: {
  recipe: ListRecipe;
  onChange: (list: GroceryListData) => void;
}) {
  const [servings, setServings] = useState(recipe.servings.toString());

  return (
    <li>
      <span>{recipe.title}</span>
      <label>
        Servings for {recipe.title}
        <input value={servings} onChange={(e) => setServings(e.target.value)} />
      </label>
      <button onClick={async () => onChange(await updateListServings(recipe.recipe_id, Number(servings)))}>
        Update {recipe.title}
      </button>
      <button onClick={async () => onChange(await removeRecipeFromList(recipe.recipe_id))}>
        Remove {recipe.title}
      </button>
    </li>
  );
}

export function GroceryList() {
  const [list, setList] = useState<GroceryListData | null>(null);

  useEffect(() => {
    getList().then(setList).catch(() => setList(null));
  }, []);

  if (list === null) return <p>Loading…</p>;
  if (list.recipes.length === 0) return <p>No recipes on your list yet. Add some from the Recipes tab.</p>;

  return (
    <div>
      <h2>Grocery List</h2>
      <section>
        <h3>Recipes</h3>
        <ul>
          {list.recipes.map((r) => (
            <RecipeRow key={r.recipe_id} recipe={r} onChange={setList} />
          ))}
        </ul>
      </section>
      <section>
        <h3>Shopping list</h3>
        <ul>
          {list.items.map((item) => (
            <li key={item.ingredient_id}>
              <strong>{item.ingredient_name}</strong>: {formatQuantities(item.quantities)}
              {item.category ? ` (${item.category})` : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `frontend/`): `npm test -- src/recipes/GroceryList.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Full frontend suite + build**

Run: `npm test` then `npm run build`
Expected: all pass; clean build.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/recipes/GroceryList.tsx frontend/src/recipes/GroceryList.test.tsx
git commit -m "feat(frontend): add grocery list screen"
```

---

## Task 10: "Add to list" action on RecipeList + wire GroceryList into App nav

**Files:** Modify `frontend/src/recipes/RecipeList.tsx`; Modify `frontend/src/recipes/RecipeList.test.tsx`; Modify `frontend/src/App.tsx`; Modify `frontend/src/App.test.tsx`.

- [ ] **Step 1: Update `frontend/src/recipes/RecipeList.test.tsx`** — append a test for the "Add to list" action (keep the existing 2 tests). Add the import for `userEvent` at the top (`import userEvent from "@testing-library/user-event";`) and append:

```tsx
it("adds a recipe to the list", async () => {
  const spy = vi
    .spyOn(global, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 1, status: "draft", recipes: [], items: [] }), { status: 200 }),
    );
  render(<RecipeList onOpen={() => {}} />);
  await userEvent.click(await screen.findByRole("button", { name: /add pancakes to list/i }));
  await waitFor(() =>
    expect(spy).toHaveBeenLastCalledWith(
      expect.stringContaining("/list/recipes"),
      expect.objectContaining({ method: "POST" }),
    ),
  );
});
```

Also add `waitFor` to the testing-library import in that file (`import { render, screen, waitFor } from "@testing-library/react";`).

- [ ] **Step 2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/recipes/RecipeList.test.tsx`
Expected: FAIL — no "add ... to list" button.

- [ ] **Step 3: Update `frontend/src/recipes/RecipeList.tsx`** to add an "Add to list" button per recipe. Replace the file with:

```tsx
import { useEffect, useState } from "react";

import { addRecipeToList, listRecipes } from "../api";
import type { RecipeSummary } from "./types";

export function RecipeList({ onOpen }: { onOpen: (id: number) => void }) {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);

  useEffect(() => {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, []);

  if (recipes === null) return <p>Loading…</p>;
  if (recipes.length === 0) return <p>No recipes yet. Add one to get started.</p>;

  return (
    <ul>
      {recipes.map((r) => (
        <li key={r.id}>
          <button onClick={() => onOpen(r.id)}>
            {r.title} ({r.servings} servings)
          </button>
          <button onClick={() => addRecipeToList(r.id)}>Add {r.title} to list</button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: Run the RecipeList test to verify it passes**

Run (from `frontend/`): `npm test -- src/recipes/RecipeList.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Update `frontend/src/App.test.tsx`** — append a test that a "Grocery List" nav entry exists (keep the existing 2 tests):

```tsx
it("has a Grocery List nav entry", async () => {
  render(<App />);
  expect(await screen.findByRole("button", { name: /grocery list/i })).toBeInTheDocument();
});
```

- [ ] **Step 6: Run it to verify it fails**

Run (from `frontend/`): `npm test -- src/App.test.tsx`
Expected: FAIL — no "Grocery List" button.

- [ ] **Step 7: Update `frontend/src/App.tsx`** to add the Grocery List view + nav. Replace the file with:

```tsx
import { useState } from "react";

import { AddRecipe } from "./recipes/AddRecipe";
import { GroceryList } from "./recipes/GroceryList";
import { RecipeDetail } from "./recipes/RecipeDetail";
import { RecipeList } from "./recipes/RecipeList";

type View =
  | { name: "list" }
  | { name: "add" }
  | { name: "grocery" }
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
      </nav>

      {view.name === "list" && (
        <RecipeList onOpen={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "add" && (
        <AddRecipe onCreated={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "grocery" && <GroceryList />}
      {view.name === "detail" && <RecipeDetail recipeId={view.id} />}
    </main>
  );
}
```

- [ ] **Step 8: Run the App test + full suite + build**

Run (from `frontend/`): `npm test` then `npm run build`
Expected: all pass (App + RecipeList + GroceryList + listApi + Phase 2 tests); clean build.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/recipes/RecipeList.tsx frontend/src/recipes/RecipeList.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): add 'add to list' action and Grocery List nav"
```

---

## Task 11: End-to-end smoke test (manual, human-run)

Not automated. Run once after the suites are green to confirm the live consolidation pipeline.

- [ ] **Step 1: Bring up the stack**

Run (from repo root): `docker compose up --build -d`. Wait for health: `curl -s http://localhost:8000/health`.

- [ ] **Step 2: Create two recipes** via the UI (`http://localhost:5173` → Add recipe), or via `POST /recipes` with manual `raw_lines`, that share at least one ingredient (e.g. both use flour) and have a unit that converts (cups/ml) plus one that doesn't (a clove/pinch).

- [ ] **Step 3: Add both to the list** (Recipes tab → "Add ... to list"), set different servings, open the **Grocery List** tab.
Expected: shared ingredients are merged and summed; compatible units combined into one quantity; incompatible units shown as "X + Y" on one line; editing a recipe's servings rescales the totals live; removing a recipe updates the list.

- [ ] **Step 4: Tear down**

Run: `docker compose down`

- [ ] **Step 5: Record the result** in the PR/commit notes. Note any conversion that looks wrong for a future `units.py` tuning pass — but consolidation correctness for common cooking units is covered by `test_units.py`, so this is a sanity check, not a gate.

---

## Self-Review

**1. Spec coverage:**
- Two migrations (`grocery_list_recipes` + `quantities` JSONB) → Tasks 2, 3.
- Pure `pint`-wrapped `units.py` core → Task 4 (with verification step).
- Per-recipe target-servings scaling (`servings / default_servings`, guarded zero) → Task 6 (`_recompute`, `test_zero_default_servings...`).
- Merge identical canonical ingredients across recipes + sum → Task 6 (`grouped` by ingredient_id → `consolidate`).
- Incompatible units kept separate → Task 4 (`test_incompatible_units_kept_separate`), surfaced in Task 9 UI (`formatQuantities`, "3 clove + 1 tbsp" test).
- `qty` null carried through → Task 4 (`test_none_qty_carried_through`), Task 9 (`formatQuantities` "as needed").
- Auto-recompute on every change (delete-and-rebuild, idempotent) → Task 6 (`_recompute`, `test_rebuild_is_idempotent`).
- Single draft singleton → Task 6 (`get_or_create_draft`, `test_get_or_create_draft_is_singleton`).
- `total_qty`/`total_unit` set only when single unit → Task 6 (`single = quantities[0] if len==1`).
- `source_recipe_ids` populated → Task 6 (`sorted(data["recipes"])`).
- 4 API endpoints (GET /list, POST/PATCH/DELETE /list/recipes), upsert-on-duplicate, 404s → Task 7.
- Category-grouped output → Task 7 (`_CATEGORY_ORDER`, `cat_key`).
- Grocery List screen + "Add to list" + nav → Tasks 9, 10.
- `pint` explicit dependency → Task 1.
- No LLM anywhere → confirmed: no task imports/mocks an LLM.

No spec requirement is left without a task.

**2. Placeholder scan:** No TBD/TODO/"add error handling" placeholders. Every code step is complete and runnable. The two verification steps (Task 4 pint API, and the conversion-constant note in Task 4 Step 5) are explicit, bounded checks against named commands — necessary because `pint`'s exact conversion factors must match the test's numeric expectations.

**3. Type/name consistency:**
- `consolidate(items) -> list[dict]` returns `{"qty", "unit"}` dicts (Task 4), consumed by `service._recompute` (Task 6) and stored in `quantities`; the Pydantic `SubQuantity(qty, unit)` (Task 5) and TS `SubQuantity` (Task 8) mirror the same shape.
- Service functions `get_or_create_draft`, `add_recipe`, `set_servings`, `remove_recipe`, `NotOnListError` (Task 6) are imported and used by the router (Task 7).
- `ListRead`/`ListItemRead`/`ListRecipeRead`/`SubQuantity` (Task 5) ↔ frontend `GroceryListData`/`ListItem`/`ListRecipe`/`SubQuantity` (Task 8) have matching field names (`ingredient_id, ingredient_name, category, quantities, source_recipe_ids, pantry_status` and `recipe_id, title, servings, default_servings`).
- Frontend api fns `getList`/`addRecipeToList`/`updateListServings`/`removeRecipeFromList` (Task 8) used by `GroceryList` (Task 9) and `RecipeList` (Task 10).
- `GroceryListRecipe` model + `quantities` column names (Tasks 2, 3) match their use in `service.py` (Task 6).
- Migration head note (`b91365f1a33d`) is consistent with the Phase 2 final state.
```

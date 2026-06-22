# Recipe search, delete, and clearer ingredient mapping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add recipe search and delete, and rework the recipe-detail page so each ingredient row is clear and its canonical-ingredient match can be fixed.

**Architecture:** Backend gains a `DELETE /recipes/{id}` endpoint (cascade-deletes ingredient rows + list membership, then recomputes the active draft) and a new `ingredients` router (`GET /ingredients?q=` search + `POST /ingredients` create). Frontend adds a client-side title filter and delete button to the recipe list, and reworks the recipe-detail rows with explicit labels plus a typeahead ingredient picker.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic (backend, `uv` + pytest), React + TypeScript + Vite + Tailwind (frontend, vitest + Testing Library).

---

## Conventions

**Backend tests** run against the isolated test Postgres on port 5544 (NOT the dev DB on 5432 — the suite's `conftest.py` drops all tables on teardown). Always run backend tests like this:

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel uv run pytest <args>
```

**Frontend tests** run with:

```bash
cd frontend && npm test -- <args>
```

---

## File Structure

**Backend:**
- Modify `backend/app/recipes/service.py` — add `RecipeNotFoundError` + `delete_recipe(db, recipe_id)`.
- Modify `backend/app/recipes/router.py` — add `DELETE /recipes/{recipe_id}`.
- Create `backend/app/ingredients/schemas.py` — `IngredientOption`, `CreateIngredientRequest`.
- Create `backend/app/ingredients/router.py` — `GET /ingredients`, `POST /ingredients`.
- Modify `backend/app/main.py` — register the ingredients router.
- Modify `backend/tests/test_recipes_router.py` — delete tests.
- Create `backend/tests/test_ingredients_router.py` — search + create tests.

**Frontend:**
- Modify `frontend/src/recipes/types.ts` — add `IngredientOption`.
- Modify `frontend/src/api.ts` — add `deleteRecipe`, `searchIngredients`, `createIngredient`.
- Modify `frontend/src/recipes/api.test.ts` — tests for the new client functions.
- Modify `frontend/src/recipes/RecipeList.tsx` — search filter + delete button.
- Modify `frontend/src/recipes/RecipeList.test.tsx` — search + delete tests.
- Create `frontend/src/recipes/IngredientPicker.tsx` — typeahead picker (search existing + create new).
- Modify `frontend/src/recipes/RecipeDetail.tsx` — labelled rows, intro, picker wiring.
- Modify `frontend/src/recipes/RecipeDetail.test.tsx` — new-label + picker tests.

---

## Task 1: Backend — delete a recipe

**Files:**
- Modify: `backend/app/recipes/service.py`
- Modify: `backend/app/recipes/router.py`
- Test: `backend/tests/test_recipes_router.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_recipes_router.py` (the imports at the top already include `Ingredient, Recipe, RecipeIngredient`; add `GroceryList, GroceryListItem, GroceryListRecipe` to that import line):

```python
def test_delete_recipe_removes_it(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}")
    assert resp.status_code == 204
    assert db_session.get(Recipe, recipe.id) is None
    app.dependency_overrides.clear()


def test_delete_recipe_404_when_missing(db_session):
    client = _client(db_session)
    resp = client.delete("/recipes/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_delete_recipe_on_list_recomputes_draft(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    draft = GroceryList(name="Draft", status="draft")
    db_session.add(draft)
    db_session.flush()
    db_session.add(GroceryListRecipe(list_id=draft.id, recipe_id=recipe.id, servings=2))
    db_session.add(
        GroceryListItem(list_id=draft.id, ingredient_id=ing.id, source_recipe_ids=[recipe.id])
    )
    db_session.flush()
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}")
    assert resp.status_code == 204
    remaining = (
        db_session.query(GroceryListItem).filter_by(list_id=draft.id).count()
    )
    assert remaining == 0
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel uv run pytest tests/test_recipes_router.py -k delete -v
```
Expected: FAIL — the DELETE route returns 405/404 and the recompute assertion fails.

- [ ] **Step 3: Add the service function**

In `backend/app/recipes/service.py`, add these imports near the top (after the existing `from app.models import ...` line):

```python
from sqlalchemy import select

from app.consolidate.service import recompute_draft
from app.models import GroceryList, Recipe, RecipeIngredient
```

(Adjust the existing `from app.models import Recipe, RecipeIngredient` line to the combined import above — keep it a single import.)

Add this exception and function to the module:

```python
class RecipeNotFoundError(Exception):
    """Raised when deleting a recipe that does not exist."""


def delete_recipe(db: Session, recipe_id: int) -> None:
    """Delete a recipe (cascading its ingredient rows + list membership) and
    rebuild the active draft so its consolidated items drop off."""
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise RecipeNotFoundError(f"recipe {recipe_id} not found")
    db.delete(recipe)
    db.flush()  # FK ON DELETE CASCADE clears recipe_ingredients + grocery_list_recipes
    draft = db.execute(
        select(GroceryList).where(GroceryList.status == "draft").order_by(GroceryList.id.desc())
    ).scalars().first()
    if draft is not None:
        recompute_draft(db)
```

- [ ] **Step 4: Add the router endpoint**

In `backend/app/recipes/router.py`, update the service import line:

```python
from app.recipes.service import (
    RecipeNotFoundError,
    create_from_manual,
    delete_recipe,
    import_from_url,
)
```

Add `Response` to the FastAPI import:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
```

Add the endpoint (place it after `list_recipes`):

```python
@router.delete("/{recipe_id}", status_code=204)
def delete_recipe_endpoint(recipe_id: int, db: Session = Depends(get_db)):
    try:
        delete_recipe(db, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel uv run pytest tests/test_recipes_router.py -v
```
Expected: PASS (all recipe-router tests, including the three new ones).

- [ ] **Step 6: Commit**

```bash
git add backend/app/recipes/service.py backend/app/recipes/router.py backend/tests/test_recipes_router.py
git commit -m "feat(recipes): DELETE /recipes/{id} cascades + recomputes draft"
```

---

## Task 2: Backend — ingredients search + create

**Files:**
- Create: `backend/app/ingredients/schemas.py`
- Create: `backend/app/ingredients/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_ingredients_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ingredients_router.py`:

```python
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Ingredient


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _seed(db_session, *names):
    for n in names:
        db_session.add(Ingredient(canonical_name=n, aliases=[]))
    db_session.flush()


def test_search_matches_substring_case_insensitive(db_session):
    _seed(db_session, "garlic", "garlic powder", "onion")
    client = _client(db_session)
    resp = client.get("/ingredients", params={"q": "GARL"})
    assert resp.status_code == 200
    names = [r["canonical_name"] for r in resp.json()]
    assert names == ["garlic", "garlic powder"]
    app.dependency_overrides.clear()


def test_search_empty_query_returns_empty(db_session):
    _seed(db_session, "garlic")
    client = _client(db_session)
    resp = client.get("/ingredients", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []
    app.dependency_overrides.clear()


def test_create_new_ingredient(db_session):
    client = _client(db_session)
    resp = client.post("/ingredients", json={"name": "Fresh Basil"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["canonical_name"] == "fresh basil"
    assert isinstance(body["id"], int)
    app.dependency_overrides.clear()


def test_create_is_idempotent_on_normalized_name(db_session):
    _seed(db_session, "basil")
    existing = db_session.query(Ingredient).filter_by(canonical_name="basil").one()
    client = _client(db_session)
    resp = client.post("/ingredients", json={"name": "Basils"})
    assert resp.status_code == 201
    assert resp.json()["id"] == existing.id
    app.dependency_overrides.clear()
```

(`normalize_name` lowercases and singularizes, so `"Fresh Basil"` → `"fresh basil"` and `"Basils"` → `"basil"`.)

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel uv run pytest tests/test_ingredients_router.py -v
```
Expected: FAIL — no `/ingredients` routes are registered (404).

- [ ] **Step 3: Create the schemas**

Create `backend/app/ingredients/schemas.py`:

```python
"""Pydantic models for the ingredients API."""

from __future__ import annotations

from pydantic import BaseModel


class IngredientOption(BaseModel):
    id: int
    canonical_name: str


class CreateIngredientRequest(BaseModel):
    name: str
```

- [ ] **Step 4: Create the router**

Create `backend/app/ingredients/router.py`:

```python
"""HTTP layer for searching and creating canonical ingredients."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingredients.normalize import normalize_name
from app.ingredients.schemas import CreateIngredientRequest, IngredientOption
from app.models import Ingredient

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientOption])
def search_ingredients(q: str = "", db: Session = Depends(get_db)):
    if not q.strip():
        return []
    rows = db.execute(
        select(Ingredient)
        .where(Ingredient.canonical_name.ilike(f"%{q.strip()}%"))
        .order_by(Ingredient.canonical_name)
        .limit(20)
    ).scalars().all()
    return [IngredientOption(id=i.id, canonical_name=i.canonical_name) for i in rows]


@router.post("", response_model=IngredientOption, status_code=201)
def create_ingredient(body: CreateIngredientRequest, db: Session = Depends(get_db)):
    normalized = normalize_name(body.name)
    existing = db.execute(
        select(Ingredient).where(Ingredient.canonical_name == normalized)
    ).scalars().first()
    if existing is None:
        existing = Ingredient(canonical_name=normalized, aliases=[])
        db.add(existing)
        db.commit()
        db.refresh(existing)
    return IngredientOption(id=existing.id, canonical_name=existing.canonical_name)
```

- [ ] **Step 5: Register the router**

In `backend/app/main.py`, add the import alongside the others:

```python
from app.ingredients.router import router as ingredients_router
```

And register it after `recipes_router`:

```python
app.include_router(ingredients_router)
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel uv run pytest tests/test_ingredients_router.py -v
```
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/ingredients/schemas.py backend/app/ingredients/router.py backend/app/main.py backend/tests/test_ingredients_router.py
git commit -m "feat(ingredients): GET /ingredients search + POST /ingredients create"
```

---

## Task 3: Frontend — API client + types

**Files:**
- Modify: `frontend/src/recipes/types.ts`
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/recipes/api.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/recipes/api.test.ts`. Update the import line at the top to:

```typescript
import { createIngredient, deleteRecipe, importRecipe, listRecipes, searchIngredients, updateIngredient } from "../api";
```

Add inside the `describe("recipe api", ...)` block:

```typescript
it("deleteRecipe issues a DELETE", async () => {
  const spy = vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await deleteRecipe(7);
  expect(spy).toHaveBeenCalledWith(
    expect.stringContaining("/recipes/7"),
    expect.objectContaining({ method: "DELETE" }),
  );
});

it("deleteRecipe throws on non-ok", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 404 }));
  await expect(deleteRecipe(7)).rejects.toThrow();
});

it("searchIngredients fetches options for a query", async () => {
  const spy = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify([{ id: 3, canonical_name: "garlic" }]), { status: 200 }),
  );
  const results = await searchIngredients("gar");
  expect(results[0].canonical_name).toBe("garlic");
  expect(spy).toHaveBeenCalledWith(expect.stringContaining("/ingredients?q=gar"));
});

it("createIngredient posts the name", async () => {
  const spy = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: 9, canonical_name: "fresh basil" }), { status: 201 }),
  );
  const opt = await createIngredient("Fresh Basil");
  expect(opt.id).toBe(9);
  expect(spy).toHaveBeenCalledWith(
    expect.stringContaining("/ingredients"),
    expect.objectContaining({ method: "POST" }),
  );
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/api.test.ts
```
Expected: FAIL — `deleteRecipe`, `searchIngredients`, `createIngredient` are not exported.

- [ ] **Step 3: Add the type**

Add to `frontend/src/recipes/types.ts` (near `RecipeSummary`):

```typescript
export interface IngredientOption {
  id: number;
  canonical_name: string;
}
```

- [ ] **Step 4: Add the client functions**

In `frontend/src/api.ts`, add `IngredientOption` to the type import on line 1 (append it to the existing import list from `"./recipes/types"`).

Add these functions (after `updateIngredient`):

```typescript
export async function deleteRecipe(id: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/recipes/${id}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status);
}

export async function searchIngredients(q: string): Promise<IngredientOption[]> {
  return json<IngredientOption[]>(
    await fetch(`${BASE_URL}/ingredients?q=${encodeURIComponent(q)}`),
  );
}

export async function createIngredient(name: string): Promise<IngredientOption> {
  const res = await fetch(`${BASE_URL}/ingredients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return json<IngredientOption>(res);
}
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/api.test.ts
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/recipes/types.ts frontend/src/api.ts frontend/src/recipes/api.test.ts
git commit -m "feat(web): deleteRecipe + ingredient search/create api clients"
```

---

## Task 4: Frontend — recipe list search + delete

**Files:**
- Modify: `frontend/src/recipes/RecipeList.tsx`
- Test: `frontend/src/recipes/RecipeList.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/recipes/RecipeList.test.tsx` (inside the `describe("RecipeList", ...)` block):

```typescript
it("filters recipes by the search query", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify([
        { id: 1, title: "Pancakes", servings: 4 },
        { id: 2, title: "Omelette", servings: 2 },
      ]),
      { status: 200 },
    ),
  );
  renderWithRouter(<RecipeList />);
  await screen.findByRole("link", { name: /pancakes/i });
  await userEvent.type(screen.getByRole("searchbox", { name: /search recipes/i }), "ome");
  expect(screen.queryByRole("link", { name: /pancakes/i })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /omelette/i })).toBeInTheDocument();
});

it("shows a no-match message when search matches nothing", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
  );
  renderWithRouter(<RecipeList />);
  await screen.findByRole("link", { name: /pancakes/i });
  await userEvent.type(screen.getByRole("searchbox", { name: /search recipes/i }), "zzz");
  expect(await screen.findByText(/no recipes match/i)).toBeInTheDocument();
});

it("deletes a recipe after confirmation and refreshes", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const spy = vi
    .spyOn(global, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(new Response("[]", { status: 200 }));
  renderWithRouter(<RecipeList />);
  await userEvent.click(await screen.findByRole("button", { name: /delete pancakes/i }));
  await waitFor(() =>
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/recipes/1"),
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
  expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
});

it("does not delete when confirmation is cancelled", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  const spy = vi
    .spyOn(global, "fetch")
    .mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    );
  renderWithRouter(<RecipeList />);
  await userEvent.click(await screen.findByRole("button", { name: /delete pancakes/i }));
  expect(spy).toHaveBeenCalledTimes(1); // only the initial list fetch
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/RecipeList.test.tsx
```
Expected: FAIL — no searchbox and no delete button.

- [ ] **Step 3: Rewrite the component**

Replace the contents of `frontend/src/recipes/RecipeList.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { addRecipeToList, deleteRecipe, listRecipes } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import type { RecipeSummary } from "./types";

export function RecipeList() {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  function load() {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }

  useEffect(load, []);

  async function remove(r: RecipeSummary) {
    if (!window.confirm(`Delete ${r.title}? This also removes it from your grocery list.`)) return;
    setError(null);
    try {
      await deleteRecipe(r.id);
      load();
    } catch {
      setError("Could not delete that recipe. Please try again.");
    }
  }

  const addAction = (
    <Link
      to="/recipes/new"
      className="inline-flex items-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
    >
      + Add recipe
    </Link>
  );

  const filtered =
    recipes?.filter((r) => r.title.toLowerCase().includes(query.trim().toLowerCase())) ?? [];

  return (
    <div>
      <PageHeader title="Recipes" action={addAction} />
      {error && <ErrorBanner message={error} />}
      {recipes === null ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : recipes.length === 0 ? (
        <EmptyState icon="📖" message="No recipes yet. Add one to get started." />
      ) : (
        <>
          <div className="mb-4">
            <Input
              type="search"
              label="Search recipes"
              placeholder="Search recipes…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {filtered.length === 0 ? (
            <EmptyState icon="🔍" message="No recipes match that search." />
          ) : (
            <ul className="flex flex-col gap-2">
              {filtered.map((r) => (
                <li key={r.id}>
                  <Card className="flex items-center gap-3">
                    <Link to={`/recipes/${r.id}`} className="font-medium text-heading hover:underline">
                      {r.title}
                    </Link>
                    <span className="text-sm text-muted">{r.servings} servings</span>
                    <Button
                      variant="secondary"
                      className="ml-auto"
                      aria-label={`Add ${r.title} to list`}
                      onClick={() => addRecipeToList(r.id)}
                    >
                      Add to list
                    </Button>
                    <Button
                      variant="link"
                      aria-label={`Delete ${r.title}`}
                      onClick={() => remove(r)}
                    >
                      🗑
                    </Button>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/RecipeList.test.tsx
```
Expected: PASS (original 4 tests + 4 new ones).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeList.tsx frontend/src/recipes/RecipeList.test.tsx
git commit -m "feat(web): search + delete on the recipe list"
```

---

## Task 5: Frontend — ingredient picker

**Files:**
- Create: `frontend/src/recipes/IngredientPicker.tsx`
- Test: `frontend/src/recipes/IngredientPicker.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/recipes/IngredientPicker.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IngredientPicker } from "./IngredientPicker";

afterEach(() => vi.restoreAllMocks());

describe("IngredientPicker", () => {
  it("searches and selects an existing ingredient", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 3, canonical_name: "garlic" }]), { status: 200 }),
    );
    const onPick = vi.fn();
    render(<IngredientPicker onPick={onPick} />);
    await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "gar");
    await userEvent.click(await screen.findByRole("button", { name: "garlic" }));
    expect(onPick).toHaveBeenCalledWith(3);
  });

  it("creates a new ingredient when none fit", async () => {
    // The picker searches on every keystroke, so use a persistent, method-aware mock:
    // GET (search) always returns no matches; POST (create) returns the new ingredient.
    const spy = vi.spyOn(global, "fetch").mockImplementation((_url, init) =>
      Promise.resolve(
        init?.method === "POST"
          ? new Response(JSON.stringify({ id: 9, canonical_name: "fresh basil" }), { status: 201 })
          : new Response("[]", { status: 200 }),
      ),
    );
    const onPick = vi.fn();
    render(<IngredientPicker onPick={onPick} />);
    await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "Fresh Basil");
    await userEvent.click(await screen.findByRole("button", { name: /create "fresh basil"/i }));
    await waitFor(() => expect(onPick).toHaveBeenCalledWith(9));
    expect(spy).toHaveBeenLastCalledWith(
      expect.stringContaining("/ingredients"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/IngredientPicker.test.tsx
```
Expected: FAIL — `IngredientPicker` does not exist.

- [ ] **Step 3: Create the component**

Create `frontend/src/recipes/IngredientPicker.tsx`:

```tsx
import { useEffect, useState } from "react";

import { createIngredient, searchIngredients } from "../api";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import type { IngredientOption } from "./types";

export function IngredientPicker({ onPick }: { onPick: (ingredientId: number) => void }) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<IngredientOption[]>([]);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setOptions([]);
      return;
    }
    let active = true;
    searchIngredients(q)
      .then((opts) => active && setOptions(opts))
      .catch(() => active && setOptions([]));
    return () => {
      active = false;
    };
  }, [query]);

  async function create() {
    const opt = await createIngredient(query.trim());
    onPick(opt.id);
  }

  const trimmed = query.trim();

  return (
    <div className="mt-2 flex flex-col gap-1 rounded-xl border border-line p-2">
      <Input
        type="search"
        label="Find ingredient"
        placeholder="Search ingredients…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className="flex flex-col">
        {options.map((o) => (
          <li key={o.id}>
            <Button variant="link" onClick={() => onPick(o.id)}>
              {o.canonical_name}
            </Button>
          </li>
        ))}
        {trimmed && (
          <li>
            <Button variant="link" onClick={create}>
              Create "{trimmed}"
            </Button>
          </li>
        )}
      </ul>
    </div>
  );
}
```

(The "Create" button label uses the raw typed text; the backend normalizes it, and the test types `"Fresh Basil"` which renders as `Create "Fresh Basil"` — matched case-insensitively by the test.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/IngredientPicker.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/IngredientPicker.tsx frontend/src/recipes/IngredientPicker.test.tsx
git commit -m "feat(web): IngredientPicker typeahead (search existing + create new)"
```

---

## Task 6: Frontend — clearer recipe-detail rows

**Files:**
- Modify: `frontend/src/recipes/RecipeDetail.tsx`
- Test: `frontend/src/recipes/RecipeDetail.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/recipes/RecipeDetail.test.tsx`. First check the file's existing imports/helpers; these tests assume the existing `renderWithRouter` + route setup used by the other tests in that file. Add:

These reuse the module-level `recipe` fixture (a row with `id: 10`, "2 cups flour") and spy on the `api` module, matching the existing tests in this file. `searchIngredients` is mocked persistently so the picker's per-keystroke searches all resolve.

```typescript
it("shows the intro and labelled fields", async () => {
  vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
  expect(await screen.findByText(/matched to/i)).toBeInTheDocument();
  expect(screen.getByText(/each line from your recipe/i)).toBeInTheDocument();
});

it("re-maps the ingredient via the picker", async () => {
  vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
  vi.spyOn(api, "searchIngredients").mockResolvedValue([{ id: 8, canonical_name: "garlic powder" }]);
  const update = vi.spyOn(api, "updateIngredient").mockResolvedValue(recipe);
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
  await userEvent.click(await screen.findByRole("button", { name: /change/i }));
  await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "gar");
  await userEvent.click(await screen.findByRole("button", { name: "garlic powder" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith(1, 10, { ingredient_id: 8 }));
});
```

NOTE: `renderWithRouter(ui, { path, initialEntries })` is the real signature (see `src/test/renderWithRouter.tsx`); the existing tests use a `show()` helper that calls it as `renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] })`. The new tests above match that shape.

ALSO update the existing "saves an edited ingredient via updateIngredient" test in this file — the rework renames the per-row save button from `Save {raw_text}` to just `Save`. Change its query on the line:

```typescript
await userEvent.click(await screen.findByRole("button", { name: /save 2 cups flour/i }));
```

to:

```typescript
await userEvent.click(await screen.findByRole("button", { name: /save/i }));
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/RecipeDetail.test.tsx
```
Expected: FAIL — no intro text, no "Matched to" label, no "Change" button.

- [ ] **Step 3: Rewrite the component**

Replace the contents of `frontend/src/recipes/RecipeDetail.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getRecipe, updateIngredient } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import { IngredientPicker } from "./IngredientPicker";
import type { IngredientRead, RecipeRead } from "./types";

function Row({
  recipeId,
  ingredient,
  onSaved,
}: {
  recipeId: number;
  ingredient: IngredientRead;
  onSaved: (recipe: RecipeRead) => void;
}) {
  const [qty, setQty] = useState(ingredient.qty?.toString() ?? "");
  const [unit, setUnit] = useState(ingredient.unit ?? "");
  const [changing, setChanging] = useState(false);

  async function save() {
    onSaved(
      await updateIngredient(recipeId, ingredient.id, {
        qty: qty === "" ? undefined : Number(qty),
        unit: unit === "" ? undefined : unit,
      }),
    );
  }

  async function remap(ingredientId: number) {
    onSaved(await updateIngredient(recipeId, ingredient.id, { ingredient_id: ingredientId }));
    setChanging(false);
  }

  return (
    <Card className={ingredient.needs_review ? "border-accent bg-tint-amber" : ""}>
      <div className="mb-2 flex items-center gap-2">
        <span className="font-medium text-heading">{ingredient.raw_text}</span>
        {ingredient.needs_review && <Pill tone="warning">Needs review</Pill>}
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted">Matched to:</span>
        <strong className="text-heading">{ingredient.ingredient_name ?? "—"}</strong>
        <Button variant="link" className="ml-auto" onClick={() => setChanging((c) => !c)}>
          Change
        </Button>
      </div>
      {changing && <IngredientPicker onPick={remap} />}

      <div className="mt-2 flex flex-wrap items-end gap-3">
        <Input label="Amount" value={qty} onChange={(e) => setQty(e.target.value)} className="w-24" />
        <Input label="Unit" value={unit} onChange={(e) => setUnit(e.target.value)} className="w-28" />
        <Button variant="secondary" onClick={save}>
          Save
        </Button>
      </div>
    </Card>
  );
}

export function RecipeDetail() {
  const { id } = useParams();
  const recipeId = Number(id);
  const [recipe, setRecipe] = useState<RecipeRead | null>(null);

  useEffect(() => {
    getRecipe(recipeId).then(setRecipe).catch(() => setRecipe(null));
  }, [recipeId]);

  if (recipe === null)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );

  const flagged = recipe.ingredients.filter((i) => i.needs_review).length;

  return (
    <div>
      <PageHeader title={recipe.title} />
      <p className="mb-2 text-sm text-muted">
        Each line from your recipe is matched to a grocery ingredient. Fix the amount or the match
        if it's wrong.
      </p>
      <p role="status" className="mb-4 text-sm text-muted">
        {flagged > 0
          ? `${flagged} item${flagged === 1 ? "" : "s"} need${flagged === 1 ? "s" : ""} review`
          : "All items reviewed ✓"}
      </p>
      <ul className="flex flex-col gap-3">
        {recipe.ingredients.map((ing) => (
          <li key={ing.id}>
            <Row recipeId={recipe.id} ingredient={ing} onSaved={setRecipe} />
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/RecipeDetail.test.tsx
```
Expected: PASS (existing tests + 2 new ones). If an existing test asserted the old bare-arrow layout or `Save {raw_text}` button label, update that assertion to the new labels ("Save", "Amount", "Unit").

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeDetail.tsx frontend/src/recipes/RecipeDetail.test.tsx
git commit -m "feat(web): clearer recipe-detail rows + fix-the-match picker"
```

---

## Task 7: Full verification

- [ ] **Step 1: Run the entire backend suite**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel uv run pytest -q
```
Expected: all tests pass.

- [ ] **Step 2: Run the entire frontend suite + build**

```bash
cd frontend && npm test && npm run build
```
Expected: all tests pass; `tsc -b && vite build` succeeds (no type errors).

- [ ] **Step 3: Manual smoke (optional but recommended)**

Use the `/run` skill or `docker compose up` to launch the app, then:
- Search the recipe list; confirm filtering and the no-match message.
- Delete a recipe that's on the grocery list; confirm it disappears from both the list and the grocery list.
- Open a recipe, click **Change** on a row, search and pick a different ingredient (and try **Create**), and confirm the "Needs review" flag clears.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** Search → Task 4; Delete (+remove from list) → Task 1 & 4; ingredients search/create endpoints → Task 2 & 3; clearer rows + fix-the-match → Task 5 & 6. All spec sections map to a task.
- **Type consistency:** `IngredientOption { id, canonical_name }` is identical across backend schema (Task 2), frontend type (Task 3), and picker (Task 5). `deleteRecipe`, `searchIngredients`, `createIngredient` names match across api client, tests, and components.
- **Known integration point:** `RecipeDetail.test.tsx` and `RecipeList.test.tsx` already exist — read each before editing and preserve their existing `renderWithRouter` call shape; update any assertion that hard-codes the old recipe-detail row layout.
```

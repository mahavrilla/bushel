# Add / remove a single recipe ingredient — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user add a single ingredient (parsed via the existing pipeline) to an existing recipe and delete a single ingredient, from the recipe detail page.

**Architecture:** A new `POST /recipes/{id}/ingredients` parses one raw line (`parse_line` → `canonicalize_names`) and appends a `RecipeIngredient`, flagged for review by the same rule as recipe creation; a new `DELETE /recipes/{id}/ingredients/{row_id}` removes one row. Both return the updated `RecipeRead`. The recipe detail page gains an add-ingredient input and a confirm-guarded per-row delete.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic (backend, `uv` + pytest), React + TypeScript + Vite (frontend, vitest + Testing Library).

---

## Conventions

**Backend tests** run against the isolated test Postgres `bushel_test` on port 5544 (NOT the dev DB on 5432 — `conftest.py` drops all tables on teardown). Always:

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
- Modify `backend/app/recipes/service.py` — extract `_needs_review` helper; add `add_ingredient`.
- Modify `backend/app/recipes/schemas.py` — add `AddIngredientRequest`.
- Modify `backend/app/recipes/router.py` — add `POST` (add) and `DELETE` (remove) ingredient endpoints.
- Tests: `backend/tests/test_recipe_service.py` (add-ingredient service behavior), `backend/tests/test_recipes_router.py` (both endpoints).

**Frontend:**
- Modify `frontend/src/api.ts` — `addIngredient`, `deleteIngredient`.
- Modify `frontend/src/recipes/RecipeDetail.tsx` — add-ingredient form + per-row delete.
- Tests: `frontend/src/recipes/api.test.ts`, `frontend/src/recipes/RecipeDetail.test.tsx`.

---

## Task 1: Backend — add an ingredient

**Files:**
- Modify: `backend/app/recipes/service.py`
- Modify: `backend/app/recipes/schemas.py`
- Modify: `backend/app/recipes/router.py`
- Test: `backend/tests/test_recipe_service.py`, `backend/tests/test_recipes_router.py`

- [ ] **Step 1: Write the failing service tests**

Add to `backend/tests/test_recipe_service.py` (it already imports `MagicMock, patch`, `ParsedLine`, `Recipe, RecipeIngredient, Ingredient`; add `add_ingredient` and `RecipeNotFoundError` to the service import line, and `import pytest`):

```python
@patch("app.recipes.service.parse_line")
def test_add_ingredient_appends_parsed_row(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(2.0, "cup", "flour", "library")
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    recipe = Recipe(title="T", default_servings=1)
    db_session.add(recipe)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"flour": CanonResult(flour.id, False)}
        add_ingredient(db_session, recipe.id, "2 cups flour", llm=MagicMock())

    rows = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
    assert len(rows) == 1
    assert rows[0].qty == 2.0 and rows[0].unit == "cup"
    assert rows[0].ingredient_id == flour.id
    assert rows[0].parse_source == "manual"  # library entry typed by hand
    assert rows[0].needs_review is False


@patch("app.recipes.service.parse_line")
def test_add_ingredient_flags_low_confidence(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(None, None, "saffron", "library_low_confidence")
    saffron = Ingredient(canonical_name="saffron", aliases=[])
    db_session.add(saffron)
    recipe = Recipe(title="T", default_servings=1)
    db_session.add(recipe)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"saffron": CanonResult(saffron.id, False)}
        add_ingredient(db_session, recipe.id, "a pinch of saffron", llm=MagicMock())

    row = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).one()
    assert row.needs_review is True
    assert row.parse_source == "library_low_confidence"


def test_add_ingredient_missing_recipe_raises(db_session):
    with pytest.raises(RecipeNotFoundError):
        add_ingredient(db_session, 99999, "1 egg", llm=MagicMock())
```

- [ ] **Step 2: Run the service tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipe_service.py -k add_ingredient -v
```
Expected: FAIL — `add_ingredient` doesn't exist.

- [ ] **Step 3: Extract `_needs_review` and add the service function**

In `backend/app/recipes/service.py`, add a `_needs_review` helper and refactor `_build_recipe` to use it, then add `add_ingredient`. Replace the `_build_recipe` body's `needs_review = (...)` expression with a call to the helper.

Add the helper (after `_LOW_CONFIDENCE_SOURCE`):

```python
def _needs_review(source: str, qty: float | None, is_new: bool) -> bool:
    """A row needs review when the parse was uncertain, the LLM was used, the quantity
    couldn't be parsed, or the ingredient is brand new."""
    return source == _LOW_CONFIDENCE_SOURCE or source == "llm" or qty is None or is_new
```

In `_build_recipe`, change:

```python
        needs_review = (
            p.source == _LOW_CONFIDENCE_SOURCE
            or p.source == "llm"
            or p.qty is None  # unparseable quantity
            or result.is_new
        )
```

to:

```python
        needs_review = _needs_review(p.source, p.qty, result.is_new)
```

Add the new function (e.g. after `create_from_manual`):

```python
def add_ingredient(db: Session, recipe_id: int, raw_text: str, llm: LLMClient) -> Recipe:
    """Parse one raw line and append it to an existing recipe as a RecipeIngredient."""
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise RecipeNotFoundError(f"recipe {recipe_id} not found")
    parsed = parse_line(raw_text, llm)
    result = canonicalize_names([parsed.name], db, llm)[parsed.name]
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            raw_text=raw_text,
            qty=parsed.qty,
            unit=parsed.unit,
            ingredient_id=result.ingredient_id,
            parse_source="manual" if parsed.source == "library" else parsed.source,
            needs_review=_needs_review(parsed.source, parsed.qty, result.is_new),
        )
    )
    db.flush()
    return recipe
```

- [ ] **Step 4: Run the service tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipe_service.py -v
```
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Write the failing router tests**

Add to `backend/tests/test_recipes_router.py` (it already imports `patch`, the models, `_client`, `_seed_recipe`):

```python
def test_add_ingredient_endpoint(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    with patch("app.recipes.router.add_ingredient") as mock_add:
        mock_add.return_value = recipe
        resp = client.post(f"/recipes/{recipe.id}/ingredients", json={"raw_text": "2 cups flour"})
    assert resp.status_code == 201
    assert resp.json()["id"] == recipe.id
    mock_add.assert_called_once()
    app.dependency_overrides.clear()


def test_add_ingredient_404_when_recipe_missing(db_session):
    from app.recipes.service import RecipeNotFoundError

    client = _client(db_session)
    with patch("app.recipes.router.add_ingredient", side_effect=RecipeNotFoundError("nope")):
        resp = client.post("/recipes/99999/ingredients", json={"raw_text": "1 egg"})
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_add_ingredient_blank_is_422(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.post(f"/recipes/{recipe.id}/ingredients", json={"raw_text": "   "})
    assert resp.status_code == 422
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Run the router tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -k add_ingredient -v
```
Expected: FAIL — no POST ingredients route / schema.

- [ ] **Step 7: Add the request schema**

In `backend/app/recipes/schemas.py`, add (the file already imports `BaseModel, field_validator`):

```python
class AddIngredientRequest(BaseModel):
    raw_text: str

    @field_validator("raw_text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_text must not be blank")
        return v.strip()
```

- [ ] **Step 8: Add the router endpoint**

In `backend/app/recipes/router.py`:
- Add `AddIngredientRequest` to the `app.recipes.schemas` import block.
- Add `add_ingredient` to the `app.recipes.service` import block.
- Add this endpoint (after `create_recipe`):

```python
@router.post("/{recipe_id}/ingredients", response_model=RecipeRead, status_code=201)
def add_ingredient_endpoint(
    recipe_id: int,
    body: AddIngredientRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    try:
        recipe = add_ingredient(db, recipe_id, body.raw_text, llm)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return _serialize(recipe, db)
```

- [ ] **Step 9: Run the router tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py tests/test_recipe_service.py -v
```
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/recipes/service.py backend/app/recipes/schemas.py backend/app/recipes/router.py backend/tests/test_recipe_service.py backend/tests/test_recipes_router.py
git commit -m "feat(recipes): POST /recipes/{id}/ingredients to add a parsed ingredient"
```

---

## Task 2: Backend — delete an ingredient

**Files:**
- Modify: `backend/app/recipes/router.py`
- Test: `backend/tests/test_recipes_router.py`

This mirrors the existing inline row-lookup pattern in `update_ingredient` (no new service function needed).

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_recipes_router.py`:

```python
def test_delete_ingredient_endpoint(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}/ingredients/{ri.id}")
    assert resp.status_code == 200
    assert resp.json()["ingredients"] == []
    assert db_session.get(RecipeIngredient, ri.id) is None
    app.dependency_overrides.clear()


def test_delete_ingredient_404_when_missing(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    client = _client(db_session)
    resp = client.delete(f"/recipes/{recipe.id}/ingredients/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_delete_ingredient_404_when_on_other_recipe(db_session):
    recipe, ri, ing = _seed_recipe(db_session)
    other = Recipe(title="Other", default_servings=1)
    db_session.add(other)
    db_session.flush()
    client = _client(db_session)
    resp = client.delete(f"/recipes/{other.id}/ingredients/{ri.id}")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -k delete_ingredient -v
```
Expected: FAIL — no DELETE ingredients route.

- [ ] **Step 3: Add the router endpoint**

In `backend/app/recipes/router.py`, add (after `update_ingredient`):

```python
@router.delete("/{recipe_id}/ingredients/{ingredient_row_id}", response_model=RecipeRead)
def delete_ingredient(recipe_id: int, ingredient_row_id: int, db: Session = Depends(get_db)):
    row = db.get(RecipeIngredient, ingredient_row_id)
    if row is None or row.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    db.delete(row)
    db.commit()
    recipe = db.get(Recipe, recipe_id)
    return _serialize(recipe, db)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/recipes/router.py backend/tests/test_recipes_router.py
git commit -m "feat(recipes): DELETE /recipes/{id}/ingredients/{row} to remove an ingredient"
```

---

## Task 3: Frontend — api client

**Files:**
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/recipes/api.test.ts`

- [ ] **Step 1: Write the failing tests**

In `frontend/src/recipes/api.test.ts`, update the import line to include the two new functions, e.g.:

```typescript
import { addIngredient, createIngredient, deleteIngredient, deleteRecipe, importRecipe, listRecipes, searchIngredients, updateIngredient } from "../api";
```

Add inside the `describe("recipe api", ...)` block:

```typescript
it("addIngredient posts the raw line to the recipe", async () => {
  const spy = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: 1, title: "X", servings: 2, source_url: null, ingredients: [] }), { status: 201 }),
  );
  await addIngredient(1, "2 cloves garlic");
  expect(spy).toHaveBeenCalledWith(
    expect.stringContaining("/recipes/1/ingredients"),
    expect.objectContaining({ method: "POST" }),
  );
});

it("deleteIngredient issues a DELETE for the row", async () => {
  const spy = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: 1, title: "X", servings: 2, source_url: null, ingredients: [] }), { status: 200 }),
  );
  await deleteIngredient(1, 10);
  expect(spy).toHaveBeenCalledWith(
    expect.stringContaining("/recipes/1/ingredients/10"),
    expect.objectContaining({ method: "DELETE" }),
  );
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/api.test.ts
```
Expected: FAIL — functions not exported.

- [ ] **Step 3: Add the client functions**

In `frontend/src/api.ts`, add after `updateIngredient`:

```typescript
export async function addIngredient(recipeId: number, rawText: string): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes/${recipeId}/ingredients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText }),
  });
  return json<RecipeRead>(res);
}

export async function deleteIngredient(recipeId: number, rowId: number): Promise<RecipeRead> {
  return json<RecipeRead>(
    await fetch(`${BASE_URL}/recipes/${recipeId}/ingredients/${rowId}`, { method: "DELETE" }),
  );
}
```

(`RecipeRead` is already imported in `api.ts`.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/api.test.ts && npx tsc -b
```
Expected: PASS, clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/recipes/api.test.ts
git commit -m "feat(web): addIngredient + deleteIngredient api clients"
```

---

## Task 4: Frontend — add input + delete button on RecipeDetail

**Files:**
- Modify: `frontend/src/recipes/RecipeDetail.tsx`
- Test: `frontend/src/recipes/RecipeDetail.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/recipes/RecipeDetail.test.tsx` (inside the `describe` block; `userEvent`, `waitFor`, `api`, `renderWithRouter` are already imported):

```typescript
it("adds an ingredient via the add form", async () => {
  vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
  const add = vi.spyOn(api, "addIngredient").mockResolvedValue({
    ...recipe,
    ingredients: [
      ...recipe.ingredients,
      { id: 11, raw_text: "2 cloves garlic", qty: 2, unit: "clove", ingredient_id: 6, ingredient_name: "garlic", parse_source: "manual", needs_review: false },
    ],
  });
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
  await screen.findByText("2 cups flour");
  await userEvent.type(screen.getByRole("textbox", { name: /add an ingredient/i }), "2 cloves garlic");
  await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
  await waitFor(() => expect(add).toHaveBeenCalledWith(1, "2 cloves garlic"));
  expect(await screen.findByText("2 cloves garlic")).toBeInTheDocument();
});

it("deletes an ingredient after confirmation", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
  const del = vi.spyOn(api, "deleteIngredient").mockResolvedValue({ ...recipe, ingredients: [] });
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
  await userEvent.click(await screen.findByRole("button", { name: /delete 2 cups flour/i }));
  await waitFor(() => expect(del).toHaveBeenCalledWith(1, 10));
  expect(screen.queryByText("2 cups flour")).not.toBeInTheDocument();
});

it("does not delete when confirmation is cancelled", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
  const del = vi.spyOn(api, "deleteIngredient").mockResolvedValue(recipe);
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
  await userEvent.click(await screen.findByRole("button", { name: /delete 2 cups flour/i }));
  expect(del).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/RecipeDetail.test.tsx
```
Expected: FAIL — no add form, no delete button.

- [ ] **Step 3: Update the component**

In `frontend/src/recipes/RecipeDetail.tsx`:

**(a)** Update the api import line:

```tsx
import { addIngredient, deleteIngredient, getRecipe, updateIngredient } from "../api";
```

**(b)** Add a delete handler + button to `Row`. Inside the `Row` function, add after `remap`:

```tsx
  async function remove() {
    if (!window.confirm(`Delete "${ingredient.raw_text}"?`)) return;
    setError(null);
    try {
      onSaved(await deleteIngredient(recipeId, ingredient.id));
    } catch {
      setError("Couldn't delete — please try again.");
    }
  }
```

Change the header row (the `mb-2 flex` div) to include a delete button:

```tsx
      <div className="mb-2 flex items-center gap-2">
        <span className="font-medium text-heading">{ingredient.raw_text}</span>
        {ingredient.needs_review && <Pill tone="warning">Needs review</Pill>}
        <Button
          variant="link"
          className="ml-auto"
          aria-label={`Delete ${ingredient.raw_text}`}
          onClick={remove}
        >
          🗑
        </Button>
      </div>
```

**(c)** Add an add-ingredient form to the `RecipeDetail` component. Add state near the `recipe` state:

```tsx
  const [newLine, setNewLine] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
```

Add an `add` function (after the `useEffect`):

```tsx
  async function add() {
    const text = newLine.trim();
    if (!text) return;
    setAddError(null);
    try {
      setRecipe(await addIngredient(recipeId, text));
      setNewLine("");
    } catch {
      setAddError("Couldn't add that ingredient — please try again.");
    }
  }
```

Render the form after the `</ul>` (and before the closing `</div>`):

```tsx
      <form
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
        className="mt-4 flex items-end gap-2"
      >
        <Input
          label="Add an ingredient"
          placeholder="e.g. 2 cloves garlic"
          value={newLine}
          onChange={(e) => setNewLine(e.target.value)}
          className="w-full"
        />
        <Button type="submit" disabled={!newLine.trim()}>
          Add
        </Button>
      </form>
      {addError && <ErrorBanner message={addError} />}
```

(`Input`, `Button`, and `ErrorBanner` are already imported in this file.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/RecipeDetail.test.tsx && npx tsc -b
```
Expected: PASS (existing + 3 new), clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeDetail.tsx frontend/src/recipes/RecipeDetail.test.tsx
git commit -m "feat(web): add-ingredient input + confirm-guarded delete on recipe detail"
```

---

## Task 5: Full verification

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

Launch the app, open a recipe: type "2 cloves garlic" into "Add an ingredient" and click Add — it appears in the list (flagged for review if uncertain). Click 🗑 on a row, confirm — it disappears. Cancel the confirm — nothing happens.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** add endpoint → Task 1; delete endpoint → Task 2; api client → Task 3; add input + confirm-guarded delete UI → Task 4. The `_needs_review` rule reuse and `parse_source = "manual" if library` are in Task 1.
- **Type/signature consistency:** `add_ingredient(db, recipe_id, raw_text, llm)` and the router call match; `addIngredient(recipeId, rawText)` / `deleteIngredient(recipeId, rowId)` match across api client, tests, and component; both return `RecipeRead`. Delete endpoint mirrors the existing `update_ingredient` 404 guard exactly.
- **Status codes:** add = 201, delete = 200 (returns updated `RecipeRead`), missing recipe/row = 404, blank raw_text = 422.
- **No new service function for delete** — intentional, mirrors the inline row-lookup pattern already used by `update_ingredient`.

# LLM ingredient extraction from pasted text — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Add-recipe page, paste a messy recipe block and extract only the ingredient lines via the LLM into the ingredients textarea for review before saving.

**Architecture:** A new `LLMClient.extract_ingredients(text)` returns clean ingredient line strings; a side-effect-free `POST /recipes/extract-ingredients` endpoint exposes it (no recipe created). The Add-recipe page gets an "Extract ingredients" button that replaces the textarea contents with the result; the existing Save path is unchanged.

**Tech Stack:** FastAPI + Pydantic + Anthropic structured output (backend, `uv` + pytest), React + TypeScript + Vite (frontend, vitest + Testing Library).

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
- Modify `backend/app/llm/client.py` — `ExtractedIngredientsLLM` model + `extract_ingredients` method.
- Modify `backend/app/recipes/service.py` — `extract_ingredient_lines` helper.
- Modify `backend/app/recipes/schemas.py` — `ExtractIngredientsRequest`, `ExtractedIngredients`.
- Modify `backend/app/recipes/router.py` — `POST /recipes/extract-ingredients`.
- Tests: `backend/tests/test_llm_client.py`, `backend/tests/test_recipes_router.py`.

**Frontend:**
- Modify `frontend/src/api.ts` — `extractIngredients`.
- Modify `frontend/src/recipes/AddRecipe.tsx` — "Extract ingredients" button + handler.
- Tests: `frontend/src/recipes/api.test.ts`, `frontend/src/recipes/AddRecipe.test.tsx`.

---

## Task 1: Backend — LLM extract_ingredients

**Files:**
- Modify: `backend/app/llm/client.py`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_llm_client.py` (add `ExtractedIngredientsLLM` to the existing `from app.llm.client import (...)` block):

```python
@patch("app.llm.client.anthropic.Anthropic")
def test_extract_ingredients_returns_lines(mock_anthropic):
    expected = ExtractedIngredientsLLM(lines=["ground turkey", "olive oil"])
    mock_anthropic.return_value.messages.parse.return_value = MagicMock(
        stop_reason="end_turn", parsed_output=expected
    )
    client = LLMClient(api_key="sk-test")
    result = client.extract_ingredients("Ingredients\n- Ground turkey\n- Olive oil\nSteps\n1. cook")
    assert result == ["ground turkey", "olive oil"]
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    assert kwargs["model"] == "claude-haiku-4-5"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_llm_client.py -k extract_ingredients -v
```
Expected: FAIL — `ExtractedIngredientsLLM` / `extract_ingredients` don't exist.

- [ ] **Step 3: Add the model + method**

In `backend/app/llm/client.py`, add the output model (near the other `*LLM` models, e.g. after `ScrapedRecipeLLM`):

```python
class ExtractedIngredientsLLM(BaseModel):
    lines: list[str]
```

Add the method to `LLMClient` (e.g. after `scrape_recipe`):

```python
    def extract_ingredients(self, text: str) -> list[str]:
        result = self._parse(
            system=(
                "You extract the ingredient list from pasted recipe text. Return only the "
                "ingredients, one per entry in `lines`. Ignore the recipe title, section "
                "headers (such as 'Ingredients' or 'Steps'), and any numbered or "
                "instructional steps. If a single line lists multiple ingredients (e.g. "
                "comma-separated), split it into one entry per ingredient. Drop preparation "
                "notes (e.g. 'cut into wedges', 'chopped'). Keep each entry short."
            ),
            user=text,
            output_format=ExtractedIngredientsLLM,
            max_tokens=1024,
        )
        return result.lines
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_llm_client.py -v
```
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/client.py backend/tests/test_llm_client.py
git commit -m "feat(llm): extract_ingredients — pull ingredient lines from pasted text"
```

---

## Task 2: Backend — service helper + endpoint

**Files:**
- Modify: `backend/app/recipes/service.py`
- Modify: `backend/app/recipes/schemas.py`
- Modify: `backend/app/recipes/router.py`
- Test: `backend/tests/test_recipes_router.py`

- [ ] **Step 1: Write the failing router tests**

Add to `backend/tests/test_recipes_router.py`:

```python
def test_extract_ingredients_endpoint(db_session):
    client = _client(db_session)
    with patch("app.recipes.router.extract_ingredient_lines") as mock_extract:
        mock_extract.return_value = ["ground turkey", "olive oil"]
        resp = client.post(
            "/recipes/extract-ingredients",
            json={"text": "Ingredients\n- Ground turkey\n- Olive oil"},
        )
    assert resp.status_code == 200
    assert resp.json()["lines"] == ["ground turkey", "olive oil"]
    app.dependency_overrides.clear()


def test_extract_ingredients_blank_is_422(db_session):
    client = _client(db_session)
    resp = client.post("/recipes/extract-ingredients", json={"text": "   "})
    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_extract_ingredients_503_when_llm_unavailable(db_session):
    from app.llm.client import LLMUnavailableError

    client = _client(db_session)
    with patch("app.recipes.router.extract_ingredient_lines", side_effect=LLMUnavailableError("no key")):
        resp = client.post("/recipes/extract-ingredients", json={"text": "stuff"})
    assert resp.status_code == 503
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -k extract_ingredients -v
```
Expected: FAIL — no route / schema / service helper.

- [ ] **Step 3: Add the service helper**

In `backend/app/recipes/service.py`, add (e.g. after `add_ingredient`):

```python
def extract_ingredient_lines(text: str, llm: LLMClient) -> list[str]:
    """Extract ingredient-only lines from pasted recipe text via the LLM."""
    return llm.extract_ingredients(text)
```

- [ ] **Step 4: Add the schemas**

In `backend/app/recipes/schemas.py`, add:

```python
class ExtractIngredientsRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v.strip()


class ExtractedIngredients(BaseModel):
    lines: list[str]
```

- [ ] **Step 5: Add the endpoint**

In `backend/app/recipes/router.py`:
- Change the LLM import to include the error: `from app.llm.client import LLMClient, LLMUnavailableError`.
- Add `ExtractIngredientsRequest, ExtractedIngredients` to the `app.recipes.schemas` import block.
- Add `extract_ingredient_lines` to the `app.recipes.service` import block.
- Add the endpoint (e.g. after `create_recipe`):

```python
@router.post("/extract-ingredients", response_model=ExtractedIngredients)
def extract_ingredients_endpoint(
    body: ExtractIngredientsRequest, llm: LLMClient = Depends(get_llm)
):
    try:
        lines = extract_ingredient_lines(body.text, llm)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Ingredient extraction unavailable: {exc}")
    return ExtractedIngredients(lines=lines)
```

(The path `/recipes/extract-ingredients` is a single literal segment; it cannot match the int-typed `/{recipe_id}` routes or the two-segment `/{recipe_id}/ingredients` add route, so route ordering is not a concern.)

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/recipes/service.py backend/app/recipes/schemas.py backend/app/recipes/router.py backend/tests/test_recipes_router.py
git commit -m "feat(recipes): POST /recipes/extract-ingredients (LLM, no side effects)"
```

---

## Task 3: Frontend — api client

**Files:**
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/recipes/api.test.ts`

- [ ] **Step 1: Write the failing test**

In `frontend/src/recipes/api.test.ts`, add `extractIngredients` to the import from `"../api"`, then add inside the `describe("recipe api", ...)` block:

```typescript
it("extractIngredients posts text and returns lines", async () => {
  const spy = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ lines: ["ground turkey", "olive oil"] }), { status: 200 }),
  );
  const lines = await extractIngredients("Ingredients\n- Ground turkey");
  expect(lines).toEqual(["ground turkey", "olive oil"]);
  expect(spy).toHaveBeenCalledWith(
    expect.stringContaining("/recipes/extract-ingredients"),
    expect.objectContaining({ method: "POST" }),
  );
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npm test -- src/recipes/api.test.ts
```
Expected: FAIL — `extractIngredients` not exported.

- [ ] **Step 3: Add the client function**

In `frontend/src/api.ts`, add (e.g. after `createRecipe`):

```typescript
export async function extractIngredients(text: string): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/recipes/extract-ingredients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const body = await json<{ lines: string[] }>(res);
  return body.lines;
}
```

- [ ] **Step 4: Run the test + typecheck**

```bash
cd frontend && npm test -- src/recipes/api.test.ts && npx tsc -b
```
Expected: PASS, clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/recipes/api.test.ts
git commit -m "feat(web): extractIngredients api client"
```

---

## Task 4: Frontend — Extract button on AddRecipe

**Files:**
- Modify: `frontend/src/recipes/AddRecipe.tsx`
- Test: `frontend/src/recipes/AddRecipe.test.tsx`

- [ ] **Step 1: Write the failing tests**

In `frontend/src/recipes/AddRecipe.test.tsx`, add `import * as api from "../api";` and `waitFor` to the testing-library import (it currently imports `render, screen`). Add these tests inside the `describe`:

```typescript
it("extracts ingredients into the textarea", async () => {
  const spy = vi.spyOn(api, "extractIngredients").mockResolvedValue(["ground turkey", "olive oil"]);
  renderAddRecipe();
  const textarea = screen.getByLabelText(/ingredients/i);
  await userEvent.type(textarea, "messy recipe block");
  await userEvent.click(screen.getByRole("button", { name: /extract ingredients/i }));
  await waitFor(() => expect(spy).toHaveBeenCalledWith("messy recipe block"));
  expect(textarea).toHaveValue("ground turkey\nolive oil");
});

it("shows an error when extraction fails", async () => {
  vi.spyOn(api, "extractIngredients").mockRejectedValue(new Error("boom"));
  renderAddRecipe();
  await userEvent.type(screen.getByLabelText(/ingredients/i), "block");
  await userEvent.click(screen.getByRole("button", { name: /extract ingredients/i }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd frontend && npm test -- src/recipes/AddRecipe.test.tsx
```
Expected: FAIL — no "Extract ingredients" button.

- [ ] **Step 3: Update the component**

In `frontend/src/recipes/AddRecipe.tsx`:
- Add `extractIngredients` to the import from `"../api"`: `import { createRecipe, extractIngredients, importRecipe } from "../api";`.
- Add an `extract` handler inside the `AddRecipe` component (after the existing `run` function):

```tsx
  async function extract() {
    setBusy(true);
    setError(null);
    try {
      const extracted = await extractIngredients(lines);
      setLines(extracted.join("\n"));
    } catch {
      setError("Couldn't extract ingredients — edit manually or try again.");
    } finally {
      setBusy(false);
    }
  }
```

- Replace the manual-card's ingredients `<label>` + textarea block and the Save button area. The current block is:

```tsx
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Ingredients (one per line)</span>
          <textarea
            className="min-h-24 rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            value={lines}
            onChange={(e) => setLines(e.target.value)}
          />
        </label>
        <Button
          disabled={!title.trim() || !lines.trim()}
          loading={busy}
          className="self-start"
          onClick={() => run(() => createRecipe(title, servings, lines.split("\n")))}
        >
          Save recipe
        </Button>
```

Replace it with (keeps "Ingredients" in the label so `getByLabelText(/ingredients/i)` still resolves; adds the Extract button):

```tsx
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Ingredients</span>
          <span className="text-xs text-muted">
            Paste a full recipe and click Extract, or enter one ingredient per line.
          </span>
          <textarea
            className="min-h-24 rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            value={lines}
            onChange={(e) => setLines(e.target.value)}
          />
        </label>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={!lines.trim()}
            loading={busy}
            className="self-start"
            onClick={extract}
          >
            Extract ingredients
          </Button>
          <Button
            disabled={!title.trim() || !lines.trim()}
            loading={busy}
            className="self-start"
            onClick={() => run(() => createRecipe(title, servings, lines.split("\n")))}
          >
            Save recipe
          </Button>
        </div>
```

(`Button` is already imported. `busy`/`error`/`lines`/`setLines` already exist in the component.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npm test -- src/recipes/AddRecipe.test.tsx && npx tsc -b
```
Expected: PASS (existing 3 + new 2), clean typecheck. The existing manual-create and import tests still pass (label still matches `/ingredients/i`; Save/Import buttons unchanged).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/AddRecipe.tsx frontend/src/recipes/AddRecipe.test.tsx
git commit -m "feat(web): Extract ingredients button on Add recipe"
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

Launch the app, go to Add recipe, paste a full recipe block (title + Ingredients + Steps) into the ingredients box, click "Extract ingredients" — the box is replaced with just the ingredient lines (compound lines split). Enter a title, click Save — the recipe is created; ingredients without quantities show "Needs review" on the detail page.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** LLM method → Task 1; endpoint (422 blank, 503 unavailable, no side effects) → Task 2; api client → Task 3; Extract button replacing textarea contents + error handling → Task 4. Title/servings stay manual; Save path unchanged.
- **Type/signature consistency:** `extract_ingredients(text) -> list[str]` (client) ← `extract_ingredient_lines(text, llm)` (service) ← endpoint returns `ExtractedIngredients {lines}`; frontend `extractIngredients(text): Promise<string[]>` reads `body.lines`. Response key `lines` consistent across backend schema, api client, and the AddRecipe handler (`extracted.join("\n")`).
- **Existing-test safety:** the AddRecipe textarea label keeps the word "Ingredients", so `getByLabelText(/ingredients/i)` in the existing manual-create test still resolves; Save/Import buttons and their names are unchanged.
- **Route safety:** `/recipes/extract-ingredients` is a literal segment, distinct from int `/{recipe_id}` and the two-segment add route.

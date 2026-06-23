# Photo-to-recipe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user create a recipe by photographing it — the photo(s) are read by Claude's vision model, built through the existing recipe pipeline, and opened on the recipe-detail page with uncertain rows flagged.

**Architecture:** A photo import is the URL-import flow with a vision call swapped in for HTML scraping. The LLM client gains a vision method returning the existing `ScrapedRecipeLLM` shape; a new `import_from_images` service function feeds it into the existing `_build_recipe`; a multipart endpoint exposes it; the Add-recipe page gains a third `Photo` segmented mode. Photos are read then discarded (no storage).

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic + Anthropic SDK (`claude-haiku-4-5`, multimodal) on the backend; React + TypeScript + Vite + Tailwind, Vitest + Testing Library on the frontend.

**Spec:** `docs/superpowers/specs/2026-06-22-photo-to-recipe-design.md`

**Backend tests run against the isolated test DB only:**
`cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest`
(Never the dev DB on 5432 — conftest drops all tables.)
**Frontend:** `cd frontend && npm test -- <file>`; type-check `npx tsc -b`; build `npm run build`.

---

## File Structure

- `backend/app/llm/client.py` (modify) — extract a shared `_invoke(content)` core; add `scrape_recipe_from_images`.
- `backend/tests/test_llm_client.py` (modify) — vision-method test.
- `backend/app/recipes/service.py` (modify) — `NoRecipeFoundError` + `import_from_images`.
- `backend/tests/test_recipe_service.py` (modify) — service tests.
- `backend/app/recipes/router.py` (modify) — `POST /recipes/import-photo`.
- `backend/tests/test_recipes_router.py` (modify) — endpoint tests.
- `backend/pyproject.toml` (modify) — add `python-multipart` (required by FastAPI for file uploads).
- `frontend/src/api.ts` (modify) — `importPhotoRecipe` helper.
- `frontend/src/recipes/AddRecipe.tsx` (modify) — third `Photo` segmented mode.
- `frontend/src/recipes/AddRecipe.test.tsx` (modify) — Photo-mode tests.

---

### Task 1: LLM client — shared content-block core + vision method

**Files:**
- Modify: `backend/app/llm/client.py`
- Test: `backend/tests/test_llm_client.py`

The current `_parse(*, system, user, output_format, max_tokens)` sends `messages=[{"role":"user","content": user}]` (a string). We extract its body into `_invoke(*, system, content, output_format, max_tokens)` that accepts `content` as either a string or a list of blocks, keep `_parse` passing the plain string (so existing string-content assertions stay valid), and add a vision method that passes image blocks.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_llm_client.py` (the `ScrapedRecipeLLM` import already exists at the top of the file):

```python
@patch("app.llm.client.anthropic.Anthropic")
def test_scrape_recipe_from_images_builds_image_blocks(mock_anthropic):
    import base64

    expected = ScrapedRecipeLLM(title="Card", servings=2, raw_lines=["1 egg"])
    mock_anthropic.return_value.messages.parse.return_value = MagicMock(
        stop_reason="end_turn", parsed_output=expected
    )
    client = LLMClient(api_key="sk-test")

    result = client.scrape_recipe_from_images(
        [(b"\x89PNG-bytes", "image/png"), (b"jpgbytes", "image/jpeg")]
    )

    assert result.title == "Card"
    _, kwargs = mock_anthropic.return_value.messages.parse.call_args
    content = kwargs["messages"][0]["content"]
    image_blocks = [b for b in content if b["type"] == "image"]
    assert len(image_blocks) == 2
    assert image_blocks[0]["source"]["type"] == "base64"
    assert image_blocks[0]["source"]["media_type"] == "image/png"
    assert image_blocks[0]["source"]["data"] == base64.standard_b64encode(b"\x89PNG-bytes").decode("ascii")
    assert image_blocks[1]["source"]["media_type"] == "image/jpeg"
    assert any(b["type"] == "text" for b in content)
    assert kwargs["model"] == "claude-haiku-4-5"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_llm_client.py::test_scrape_recipe_from_images_builds_image_blocks -v`
Expected: FAIL — `AttributeError: 'LLMClient' object has no attribute 'scrape_recipe_from_images'`.

- [ ] **Step 3: Implement**

In `backend/app/llm/client.py`, add `import base64` near the top (after `from __future__ import annotations`). Replace the existing `_parse` method body by introducing `_invoke` and making `_parse` delegate. The current method is:

```python
    def _parse(self, *, system: str, user: str, output_format: type[_T], max_tokens: int) -> _T:
        client = self._ensure()
        try:
            resp = client.messages.parse(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output_format,
            )
        except anthropic.APIError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            raise LLMUnavailableError("LLM refused or returned no structured output")
        return resp.parsed_output
```

Replace it with:

```python
    def _invoke(self, *, system: str, content, output_format: type[_T], max_tokens: int) -> _T:
        """Send one user message (string or content-block list) and return parsed output."""
        client = self._ensure()
        try:
            resp = client.messages.parse(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_format=output_format,
            )
        except anthropic.APIError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            raise LLMUnavailableError("LLM refused or returned no structured output")
        return resp.parsed_output

    def _parse(self, *, system: str, user: str, output_format: type[_T], max_tokens: int) -> _T:
        return self._invoke(
            system=system, content=user, output_format=output_format, max_tokens=max_tokens
        )
```

Then add this public method (alongside the other public methods, e.g. after `scrape_recipe`):

```python
    def scrape_recipe_from_images(self, images: list[tuple[bytes, str]]) -> ScrapedRecipeLLM:
        """Read a recipe from one or more photos. Each tuple is (raw_bytes, media_type)."""
        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(data).decode("ascii"),
                },
            }
            for data, media_type in images
        ]
        content.append(
            {
                "type": "text",
                "text": (
                    "Read the recipe from the attached photo(s). Return the title, the number "
                    "of servings (integer, or null), and raw_lines: the ingredient lines "
                    "exactly as written, one string per ingredient. If several photos are "
                    "attached, treat them as one recipe. Ignore instructions, steps, and page "
                    "furniture."
                ),
            }
        )
        return self._invoke(
            system=(
                "You extract a recipe from photos of a recipe — a cookbook page, a handwritten "
                "card, or a screenshot."
            ),
            content=content,
            output_format=ScrapedRecipeLLM,
            max_tokens=4096,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_llm_client.py -v`
Expected: PASS — the new test plus all existing ones (the existing string-content assertions still hold because `_parse` still passes a plain string).

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/client.py backend/tests/test_llm_client.py
git commit -m "feat(llm): vision method to read a recipe from photos"
```

---

### Task 2: Service — `import_from_images`

**Files:**
- Modify: `backend/app/recipes/service.py`
- Test: `backend/tests/test_recipe_service.py`

Mirrors `import_from_url`: call the vision method, then the existing `_build_recipe` with `source_url=None`. Raise a dedicated error when the photos yield no ingredients.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_recipe_service.py` (the file already imports `MagicMock`, `patch`, `pytest`, `Recipe`, `RecipeIngredient`, `Ingredient`, and defines `_stub_parse`):

```python
@patch("app.recipes.service.parse_line", side_effect=_stub_parse)
def test_import_from_images_builds_recipe(mock_parse, db_session):
    from app.llm.client import ScrapedRecipeLLM
    from app.ingredients.canonicalize import CanonResult
    from app.recipes.service import import_from_images

    llm = MagicMock()
    llm.scrape_recipe_from_images.return_value = ScrapedRecipeLLM(
        title="Card", servings=2, raw_lines=["1 egg"]
    )
    egg = Ingredient(canonical_name="egg", aliases=[])
    db_session.add(egg)
    db_session.flush()

    with patch(
        "app.recipes.service.canonicalize_names",
        return_value={"egg": CanonResult(egg.id, False)},
    ):
        recipe = import_from_images([(b"pngbytes", "image/png")], db=db_session, llm=llm)

    saved = db_session.get(Recipe, recipe.id)
    assert saved.title == "Card"
    assert saved.default_servings == 2
    assert saved.source_url is None
    items = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
    assert [i.raw_text for i in items] == ["1 egg"]
    llm.scrape_recipe_from_images.assert_called_once_with([(b"pngbytes", "image/png")])


def test_import_from_images_raises_when_no_ingredients(db_session):
    from app.llm.client import ScrapedRecipeLLM
    from app.recipes.service import import_from_images, NoRecipeFoundError

    llm = MagicMock()
    llm.scrape_recipe_from_images.return_value = ScrapedRecipeLLM(
        title="Blurry", servings=None, raw_lines=[]
    )
    with pytest.raises(NoRecipeFoundError):
        import_from_images([(b"pngbytes", "image/png")], db=db_session, llm=llm)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipe_service.py -k import_from_images -v`
Expected: FAIL — `ImportError: cannot import name 'import_from_images'` / `'NoRecipeFoundError'`.

- [ ] **Step 3: Implement**

In `backend/app/recipes/service.py`, add the exception next to `RecipeNotFoundError`:

```python
class NoRecipeFoundError(Exception):
    """Raised when no ingredients could be read from the photos."""
```

And add this function after `import_from_url`:

```python
def import_from_images(
    images: list[tuple[bytes, str]], *, db: Session, llm: LLMClient
) -> Recipe:
    """Read a recipe from photo bytes and build it through the standard pipeline."""
    scraped = llm.scrape_recipe_from_images(images)
    if not scraped.raw_lines:
        raise NoRecipeFoundError("no ingredients found in the photos")
    return _build_recipe(
        title=scraped.title,
        servings=scraped.servings or 1,
        source_url=None,
        raw_lines=scraped.raw_lines,
        db=db,
        llm=llm,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipe_service.py -v`
Expected: PASS — both new tests plus the existing service tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/recipes/service.py backend/tests/test_recipe_service.py
git commit -m "feat(recipes): import_from_images service for photo-based creation"
```

---

### Task 3: Endpoint — `POST /recipes/import-photo`

**Files:**
- Modify: `backend/app/recipes/router.py`
- Modify: `backend/pyproject.toml` (add `python-multipart`)
- Test: `backend/tests/test_recipes_router.py`

FastAPI needs `python-multipart` to accept file uploads. The endpoint validates type/count, reads bytes, and delegates to `import_from_images`.

- [ ] **Step 1: Add the multipart dependency**

Run: `cd backend && uv add python-multipart`
Expected: `pyproject.toml` gains `python-multipart` under dependencies and `uv.lock` updates.

- [ ] **Step 2: Write the failing tests**

Add to `backend/tests/test_recipes_router.py` (it already imports `ANY`, `patch`, `TestClient`, `app`, `Recipe`, and defines `_client`):

```python
def test_import_photo_endpoint(db_session):
    client = _client(db_session)
    with patch("app.recipes.router.import_from_images") as mock_import:
        recipe = Recipe(title="FromPhoto", default_servings=2)
        db_session.add(recipe)
        db_session.flush()
        mock_import.return_value = recipe
        resp = client.post(
            "/recipes/import-photo",
            files=[("files", ("card.png", b"pngbytes", "image/png"))],
        )
    assert resp.status_code == 201
    assert resp.json()["title"] == "FromPhoto"
    mock_import.assert_called_once_with([(b"pngbytes", "image/png")], db=db_session, llm=ANY)
    app.dependency_overrides.clear()


def test_import_photo_rejects_unsupported_type(db_session):
    client = _client(db_session)
    resp = client.post(
        "/recipes/import-photo",
        files=[("files", ("photo.heic", b"heicbytes", "image/heic"))],
    )
    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_import_photo_requires_a_file(db_session):
    client = _client(db_session)
    resp = client.post("/recipes/import-photo")
    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_import_photo_503_when_llm_unavailable(db_session):
    from app.llm.client import LLMUnavailableError

    client = _client(db_session)
    with patch("app.recipes.router.import_from_images", side_effect=LLMUnavailableError("no key")):
        resp = client.post(
            "/recipes/import-photo",
            files=[("files", ("card.png", b"x", "image/png"))],
        )
    assert resp.status_code == 503
    app.dependency_overrides.clear()


def test_import_photo_422_when_no_recipe_found(db_session):
    from app.recipes.service import NoRecipeFoundError

    client = _client(db_session)
    with patch("app.recipes.router.import_from_images", side_effect=NoRecipeFoundError("empty")):
        resp = client.post(
            "/recipes/import-photo",
            files=[("files", ("card.png", b"x", "image/png"))],
        )
    assert resp.status_code == 422
    app.dependency_overrides.clear()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -k import_photo -v`
Expected: FAIL — 404 (route does not exist yet).

- [ ] **Step 4: Implement**

In `backend/app/recipes/router.py`, update the imports. Change the FastAPI import line:

```python
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
```

Add to the existing `from app.recipes.service import (...)` block the two new names:

```python
from app.recipes.service import (
    RecipeNotFoundError,
    NoRecipeFoundError,
    add_ingredient,
    create_from_manual,
    delete_recipe,
    extract_ingredient_lines,
    import_from_images,
    import_from_url,
)
```

Add these module-level constants just below `router = APIRouter(...)`:

```python
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_PHOTOS = 5
```

Add the endpoint (e.g. right after `import_recipe`):

```python
@router.post("/import-photo", response_model=RecipeRead, status_code=201)
async def import_photo(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    if not files:
        raise HTTPException(status_code=422, detail="At least one photo is required")
    if len(files) > _MAX_PHOTOS:
        raise HTTPException(status_code=422, detail=f"At most {_MAX_PHOTOS} photos are allowed")
    images: list[tuple[bytes, str]] = []
    for f in files:
        if f.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=422, detail="Photos must be JPEG, PNG, WebP, or GIF."
            )
        data = await f.read()
        if not data:
            raise HTTPException(status_code=422, detail="One of the photos was empty.")
        images.append((data, f.content_type))
    try:
        recipe = import_from_images(images, db=db, llm=llm)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Photo import unavailable: {exc}")
    except NoRecipeFoundError:
        raise HTTPException(
            status_code=422,
            detail="Couldn't read a recipe from those photos. Try a clearer photo or enter it manually.",
        )
    db.commit()
    return _serialize(recipe, db)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_recipes_router.py -v`
Expected: PASS — the five new tests plus all existing router tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/recipes/router.py backend/pyproject.toml backend/uv.lock backend/tests/test_recipes_router.py
git commit -m "feat(recipes): POST /recipes/import-photo multipart endpoint"
```

---

### Task 4: Frontend API helper — `importPhotoRecipe`

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Implement the helper**

In `frontend/src/api.ts`, add after `importRecipe` (the `json` helper and `BASE_URL` already exist):

```typescript
export async function importPhotoRecipe(files: File[]): Promise<RecipeRead> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const res = await fetch(`${BASE_URL}/recipes/import-photo`, {
    method: "POST",
    body: form,
  });
  return json<RecipeRead>(res);
}
```

(No `Content-Type` header — the browser sets the multipart boundary automatically.)

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat(web): importPhotoRecipe api helper"
```

---

### Task 5: Frontend — Photo mode on the Add recipe page

**Files:**
- Modify: `frontend/src/recipes/AddRecipe.tsx`
- Test: `frontend/src/recipes/AddRecipe.test.tsx`

Add a third `Photo` segment. The card has a multi-file image input, a thumbnail strip with per-photo remove, and a **Create from photos** button that uploads and navigates to the new recipe. **Note on `capture`:** the spec mentioned `capture="environment"`, but since we want *multiple* photos, we omit `capture` — on iOS that yields the action sheet (Photo Library / Take Photo), which both allows multi-select from the library and still offers the camera. `capture` would force single-shot camera and is dropped intentionally.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/recipes/AddRecipe.test.tsx`, add a `beforeAll` shim for object URLs (jsdom lacks them) right after the existing `afterEach`:

```tsx
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:mock"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});
```

(Update the existing vitest import line to include `beforeAll`.) Then add these tests inside `describe("AddRecipe", ...)`:

```tsx
it("shows photo mode without the url or title fields", async () => {
  renderAddRecipe();
  await userEvent.click(screen.getByRole("tab", { name: /photo/i }));
  expect(screen.getByLabelText(/add recipe photos/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/recipe url/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^title$/i)).not.toBeInTheDocument();
});

it("creates a recipe from photos and navigates to it", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ id: 21, title: "Card", servings: 2, source_url: null, ingredients: [] }),
      { status: 201 },
    ),
  );
  renderAddRecipe();
  await userEvent.click(screen.getByRole("tab", { name: /photo/i }));
  const file = new File(["bytes"], "card.png", { type: "image/png" });
  await userEvent.upload(screen.getByLabelText(/add recipe photos/i), file);
  await userEvent.click(screen.getByRole("button", { name: /create from photos/i }));
  expect(await screen.findByText(/detail screen/i)).toBeInTheDocument();
});

it("shows an error when photo import fails", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 422 }));
  renderAddRecipe();
  await userEvent.click(screen.getByRole("tab", { name: /photo/i }));
  const file = new File(["bytes"], "card.png", { type: "image/png" });
  await userEvent.upload(screen.getByLabelText(/add recipe photos/i), file);
  await userEvent.click(screen.getByRole("button", { name: /create from photos/i }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- AddRecipe`
Expected: FAIL — no `Photo` tab / no `add recipe photos` input yet.

- [ ] **Step 3: Implement**

Replace the entire contents of `frontend/src/recipes/AddRecipe.tsx` with:

```tsx
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createRecipe, extractIngredients, importPhotoRecipe, importRecipe } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { CloseIcon } from "../components/ui/icons";

const IMPORT_ERROR = "Couldn't import — check the URL or try manual entry.";
const PHOTO_ERROR = "Couldn't read those photos — try a clearer photo or enter it manually.";

export function AddRecipe() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"url" | "manual" | "photo">("url");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [servings, setServings] = useState(1);
  const [lines, setLines] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const previews = useMemo(
    () => photos.map((file) => ({ file, url: URL.createObjectURL(file) })),
    [photos],
  );
  useEffect(
    () => () => previews.forEach((p) => URL.revokeObjectURL(p.url)),
    [previews],
  );

  async function run(action: () => Promise<{ id: number }>, errorMessage = IMPORT_ERROR) {
    setBusy(true);
    setError(null);
    try {
      const recipe = await action();
      navigate(`/recipes/${recipe.id}`);
    } catch {
      setError(errorMessage);
    } finally {
      setBusy(false);
    }
  }

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

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Add recipe" />
      <SegmentedControl
        options={[
          { value: "url", label: "URL" },
          { value: "manual", label: "Manual" },
          { value: "photo", label: "Photo" },
        ]}
        value={mode}
        onChange={setMode}
      />
      {error && <ErrorBanner message={error} />}

      {mode === "url" && (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Import by URL</h3>
          <Input label="Recipe URL" value={url} onChange={(e) => setUrl(e.target.value)} />
          <Button disabled={!url} loading={busy} className="self-start" onClick={() => run(() => importRecipe(url))}>
            Import
          </Button>
        </Card>
      )}

      {mode === "manual" && (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Enter manually</h3>
          <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input
            label="Servings"
            type="number"
            value={servings}
            onChange={(e) => setServings(Number(e.target.value))}
          />
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor="ingredients" className="font-medium text-heading">
              Ingredients
            </label>
            <p id="ingredients-hint" className="text-xs text-muted">
              Paste a full recipe and click Extract, or enter one ingredient per line.
            </p>
            <textarea
              id="ingredients"
              aria-describedby="ingredients-hint"
              className="min-h-24 rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              value={lines}
              onChange={(e) => setLines(e.target.value)}
            />
          </div>
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
        </Card>
      )}

      {mode === "photo" && (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">From a photo</h3>
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor="photos" className="font-medium text-heading">
              Add recipe photos
            </label>
            <p className="text-xs text-muted">
              Snap or pick one or more photos of the recipe. They’re read once and not stored.
            </p>
            <input
              id="photos"
              type="file"
              accept="image/*"
              multiple
              className="text-sm"
              onChange={(e) => {
                const chosen = Array.from(e.target.files ?? []);
                if (chosen.length) setPhotos((prev) => [...prev, ...chosen]);
                e.target.value = "";
              }}
            />
          </div>
          {previews.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {previews.map((p, i) => (
                <li key={p.url} className="relative">
                  <img src={p.url} alt={`Photo ${i + 1}`} className="h-20 w-20 rounded-lg object-cover" />
                  <button
                    type="button"
                    aria-label={`Remove photo ${i + 1}`}
                    onClick={() => setPhotos((prev) => prev.filter((_, j) => j !== i))}
                    className="absolute -right-1.5 -top-1.5 rounded-full bg-surface p-0.5 text-muted shadow"
                  >
                    <CloseIcon size={16} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Button
            disabled={photos.length === 0}
            loading={busy}
            className="self-start"
            onClick={() => run(() => importPhotoRecipe(photos), PHOTO_ERROR)}
          >
            Create from photos
          </Button>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- AddRecipe`
Expected: PASS — the three new tests plus all existing AddRecipe tests (URL default and Manual-tab tests are unaffected).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/AddRecipe.tsx frontend/src/recipes/AddRecipe.test.tsx
git commit -m "feat(web): Photo mode on add recipe (capture or pick, multi-photo)"
```

---

### Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest`
Expected: PASS — all tests, no regressions.

- [ ] **Step 2: Frontend suite**

Run: `cd frontend && npm test`
Expected: PASS — all suites green.

- [ ] **Step 3: Type-check + build**

Run: `cd frontend && npx tsc -b && npm run build`
Expected: no type errors; build succeeds.

- [ ] **Step 4: No commit unless incidental changes**

```bash
git status --short
# If nothing to commit, the plan is complete.
```

---

## Notes for the implementer

- Backend tests MUST use the isolated test DB (`...@localhost:5544/bushel_test`). If it isn't running:
  `docker run -d --name bushel-test-pg -e POSTGRES_USER=bushel -e POSTGRES_PASSWORD=bushel -e POSTGRES_DB=bushel_test -p 5544:5432 postgres:16`
- Don't change any existing `aria-label`, the `ingredients`/`ingredients-hint` ids, or the `role="tab"` labels the existing tests depend on.
- The `_parse` method must keep passing a **string** as `content` (not a block list) so the existing `test_canonicalize_*` / `test_scrape_recipe_truncates_html` substring assertions stay valid. Only `scrape_recipe_from_images` passes block content.
- `ScrapedRecipeLLM` and `_build_recipe` are reused unchanged — no new persistence logic.
```

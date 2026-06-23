# Photo-to-recipe — design

Date: 2026-06-22

## Goal

Let the user create a recipe by photographing it — a cookbook page, a handwritten card, or a
screenshot — instead of pasting a URL or typing it. The photo(s) are read by Claude's vision
model into a structured recipe, which is built through the *existing* recipe pipeline and
opened on the recipe-detail page with uncertain rows flagged for review. Same end state as URL
import.

## Background / current state

- **Add recipe page** (`frontend/src/recipes/AddRecipe.tsx`) already has a `SegmentedControl`
  `[URL · Manual]` with `mode: "url" | "manual"` (default `"url"`); only the active mode's card
  renders.
- **Recipe pipeline** (`backend/app/recipes/service.py`): `import_from_url` and
  `create_from_manual` both delegate to `_build_recipe(*, title, servings, source_url,
  raw_lines, db, llm)`, which runs parse → canonicalize → persist and sets `needs_review` on
  uncertain rows. `import_from_url` first calls `scrape_url` → the LLM's `scrape_recipe(html,
  url) -> ScrapedRecipeLLM { title, servings, raw_lines }`.
- **LLM client** (`backend/app/llm/client.py`): the single Anthropic integration point. Model
  is `claude-haiku-4-5` (multimodal). A private `_parse(*, system, user: str, output_format,
  max_tokens)` wraps `client.messages.parse(... messages=[{"role":"user","content": user}]
  ...)` and raises `LLMUnavailableError` on API error/refusal. All public methods funnel
  through it.
- **Router** (`backend/app/recipes/router.py`): endpoints depend on `get_llm()` (overridable in
  tests). `_serialize(recipe, db) -> RecipeRead`.

No recipe is stored with image data today; recipes carry an optional `source_url` only.

## Architecture

A photo import is the URL-import flow with a vision call swapped in for HTML scraping. It
reuses `_build_recipe`, the `ScrapedRecipeLLM` output shape, and the recipe-detail review UI
unchanged.

### Backend

**1. LLM client — content-block generalization + vision method.**
- Refactor `_parse` to delegate to a new private `_parse_blocks(*, system, content: list,
  output_format, max_tokens)` that passes `messages=[{"role":"user","content": content}]`. The
  existing `_parse` becomes `_parse_blocks(..., content=[{"type":"text","text": user}])`. No
  behavior change for existing callers (verified by their tests still passing).
- Add `scrape_recipe_from_images(images: list[tuple[bytes, str]]) -> ScrapedRecipeLLM` where
  each tuple is `(raw_bytes, media_type)`. It builds content blocks — one image block per
  photo using base64 source (`{"type":"image","source":{"type":"base64","media_type": mt,
  "data": b64}}`) followed by a text instruction — and calls `_parse_blocks` with
  `output_format=ScrapedRecipeLLM`, `max_tokens=4096`. Instruction: read the recipe from the
  attached photo(s); return the title, servings (integer or null), and `raw_lines` (the
  ingredient lines exactly as written, one string each); if several photos are given, treat
  them as one recipe; ignore instructions/steps.

**2. Service — `import_from_images`.**
```
def import_from_images(images: list[tuple[bytes, str]], *, db, llm) -> Recipe:
    scraped = llm.scrape_recipe_from_images(images)
    if not scraped.raw_lines:
        raise NoRecipeFoundError("no ingredients found in the photos")
    return _build_recipe(title=scraped.title, servings=scraped.servings or 1,
                         source_url=None, raw_lines=scraped.raw_lines, db=db, llm=llm)
```
Add a `NoRecipeFoundError` exception in the service. `source_url=None` makes library hits
record `parse_source="manual"`, consistent with a hand-entered origin.

**3. Endpoint — `POST /recipes/import-photo`.**
- Signature: `files: list[UploadFile] = File(...)`, `db`, `llm`.
- Read each `UploadFile` into bytes and take its `content_type` as the media type.
- Validation (→ `HTTPException`):
  - no files, or > 5 files → 422.
  - any file whose content type is not one of `image/jpeg`, `image/png`, `image/webp`,
    `image/gif` → 422 with a message naming the allowed types. (iOS Safari transcodes HEIC to
    JPEG on file-input upload, so this is a safety net, not the common path.)
  - empty file bytes → 422.
  - `LLMUnavailableError` → 503; `NoRecipeFoundError` → 422 "Couldn't read a recipe from those
    photos. Try a clearer photo or enter it manually."
- On success: `db.commit()`, return `_serialize(recipe, db)` with status 201.

### Frontend

`AddRecipe.tsx`:
- `mode` type becomes `"url" | "manual" | "photo"`; add a third `SegmentedControl` option
  `{ value: "photo", label: "Photo" }`. Default stays `"url"`.
- New **Photo** card (rendered when `mode === "photo"`):
  - `<input type="file" accept="image/*" capture="environment" multiple>` (a labelled control;
    on iOS this offers camera or photo library).
  - Local `files: File[]` state; selecting appends to it. A thumbnail strip (object-URL
    previews) where each photo has a remove ✕ button. Revoke object URLs on removal/unmount.
  - **Create from photos** `Button` — disabled when `files.length === 0`, `loading` while
    uploading. On click: build `FormData`, append each file under `files`, `POST` to
    `/recipes/import-photo`, then `navigate('/recipes/' + id)`. Failures set the page `error`
    (shown by the existing `ErrorBanner`).
- New API helper `importPhotoRecipe(files: File[]): Promise<RecipeRead>` in `frontend/src/api.ts`
  that posts `multipart/form-data` (no explicit `Content-Type` header — the browser sets the
  multipart boundary).

## Data flow & errors

Photos travel as multipart bytes → endpoint → `import_from_images` → `scrape_recipe_from_images`
(vision) → `_build_recipe` (parse/canonicalize/persist, flags `needs_review`) →
`_serialize` → frontend navigates to the detail page. Photos are not persisted — read and
discarded. All error states surface as HTTP errors mapped to the frontend `ErrorBanner`, matching
the existing URL/extract flows. The recipe-detail page's needs-review section (already shipped)
is where the user corrects any misreads.

## Testing

**Backend**
- `LLMClient.scrape_recipe_from_images` builds one image block per photo with the right base64
  media types + a text block (assert the constructed `content` shape against a mock Anthropic
  client; assert existing string `_parse` callers are unchanged).
- `import_from_images` builds the expected rows from a fake LLM returning a `ScrapedRecipeLLM`;
  empty `raw_lines` → `NoRecipeFoundError`.
- Endpoint: a tiny in-memory PNG with a stubbed `get_llm` override → 201 with the recipe;
  no files → 422; an unsupported content type (e.g. `image/heic`) → 422; `>5` files → 422.

**Frontend**
- AddRecipe: selecting Photo mode shows the file input and hides URL/Manual fields; choosing
  files enables **Create from photos**; clicking posts `FormData` to `/recipes/import-photo`
  and navigates to the detail route; a failed upload shows the error banner. (File selection
  simulated via `userEvent.upload`.)

## Scope / non-goals

- **No image storage** — photos are not saved with the recipe (no thumbnails on the detail
  page); recipes keep only their existing fields.
- **No in-app cropping, rotation, or HEIC transcoding** — rely on the browser; reject
  unsupported types with a clear message.
- **No new review UI** — reuses the recipe-detail needs-review flow as-is.
- Reuses `SegmentedControl`, `_build_recipe`, `ScrapedRecipeLLM`, and `_serialize`; the only
  genuinely new code is the vision LLM method, `import_from_images`, the endpoint, the Photo
  card, and the API helper.

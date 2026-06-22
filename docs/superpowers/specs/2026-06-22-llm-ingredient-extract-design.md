# LLM ingredient extraction from pasted text — design

Date: 2026-06-22

## Goal

On the Add-recipe page, let the user paste a messy recipe block (title + ingredients +
steps) and extract **only** the ingredient lines via the LLM, dropping the title, section
headers, and numbered steps, and splitting compound lines. The extracted lines fill the
ingredients textarea for review/edit before the user saves the recipe through the existing
manual-create flow.

Example input the user gave:

```
2. TURKEY BURGER LETTUCE WRAPS + SWEET POTATO WEDGES

Ingredients
- Ground turkey
- Garlic powder, onion powder, salt, pepper
- Large lettuce leaves (romaine or butter)
- Sweet potatoes, cut into wedges
- Olive oil

Steps
1. Heat oven to 425 F.
...
```

Expected extraction (ingredients only, compound line split, prep notes stripped):
`["ground turkey", "garlic powder", "onion powder", "salt", "pepper",
"large lettuce leaves", "sweet potatoes", "olive oil"]`.

## Background / current state

- **`LLMClient`** (`backend/app/llm/client.py`) wraps Anthropic structured output via a
  private `_parse(system, user, output_format, max_tokens)` helper. It already has
  `parse_ingredient_line`, `canonicalize_ingredients`, and `scrape_recipe` (which extracts
  a recipe from HTML into `{title, servings, raw_lines}`). `LLMUnavailableError` is raised
  on no-key/API-error/refusal.
- **Recipes API / service**: `POST /recipes` (manual) takes `{title, servings, raw_lines}`
  and runs `create_from_manual` → `_build_recipe` (per-line `parse_line` → `canonicalize_names`).
  Routers map Kroger "unavailable" to 503 and validation to 422; recipe import maps
  `ScrapeError` to 422.
- **Frontend** `AddRecipe.tsx`: an Import-by-URL card and a manual card with `title`,
  `servings`, and an "Ingredients (one per line)" `<textarea>` (state `lines`), a `run()`
  helper that calls an action then navigates to `/recipes/{id}`, and `createRecipe(title,
  servings, lines.split("\n"))`. `api.ts` has `createRecipe`, `importRecipe`, etc.

## Architecture / approach

Extraction is a **separate, side-effect-free step** from creation: the new endpoint returns
clean ingredient line strings and creates nothing. The frontend drops those lines into the
existing ingredients textarea, and the unchanged `createRecipe` path saves them. This reuses
the entire parse→canonicalize→persist pipeline, gives the user a review/edit gate (the
textarea) with no new dialog, and degrades gracefully when the LLM is unavailable (the user
can still type lines by hand and save).

## Backend changes

### LLM method
- Add to `LLMClient`: a Pydantic output model
  `ExtractedIngredientsLLM(BaseModel): lines: list[str]`, and a method
  `extract_ingredients(self, text: str) -> list[str]` that calls `_parse(...)` and returns
  `result.lines`. System prompt instructs: extract only the ingredient lines from pasted
  recipe text; ignore the recipe title, section headers (e.g. "Ingredients", "Steps"), and
  numbered/instructional steps; split a single line listing multiple ingredients (e.g.
  comma-separated) into one entry per ingredient; remove prep notes (e.g. "cut into
  wedges"); keep each ingredient as a short line, lowercase not required. `max_tokens` ~1024.

### Service
- New `extract_ingredient_lines(text: str, llm: LLMClient) -> list[str]` in
  `recipes/service.py` — delegates to `llm.extract_ingredients(text)` and returns the list.
  Kept in the service layer so the router stays thin and tests can mock it at the router's
  import site (mirroring how `create_from_manual` / `import_from_url` are mocked).

### Endpoint
- `POST /recipes/extract-ingredients` (`recipes/router.py`): body
  `ExtractIngredientsRequest { text: str }` (validator rejects blank/whitespace → 422,
  strips). Response model `ExtractedIngredients { lines: list[str] }`. Calls the service;
  on `LLMUnavailableError` raise `HTTPException(503, ...)`. Does not touch the DB and does
  not create anything.

## Frontend changes (`AddRecipe.tsx`)

- The manual card's ingredients `<textarea>` now doubles as a paste target. Update its label/
  hint to: "Paste a full recipe and click Extract, or enter one ingredient per line."
- Add an **"Extract ingredients"** `Button` near the textarea. On click: call
  `extractIngredients(lines)` (the current textarea content), and on success set the
  textarea state to `result.join("\n")`. Show a loading state on the button; on failure set
  an error ("Couldn't extract — edit manually or try again") shown via the existing
  `ErrorBanner`. Disable the button when the textarea is empty.
- "Save recipe" is unchanged: `createRecipe(title, servings, lines.split("\n"))`.
- `api.ts`: `extractIngredients(text: string): Promise<string[]>` →
  `POST /recipes/extract-ingredients`, returns `body.lines`.

## Testing (TDD)

- **Backend:**
  - LLM client test (`tests/test_llm_client.py` style — mock the Anthropic client/`_parse`):
    `extract_ingredients` returns the `lines` list from the structured output.
  - Router test (`tests/test_recipes_router.py`): `POST /recipes/extract-ingredients` with
    `extract_ingredient_lines` (or the LLM) mocked returns `{lines: [...]}`; blank text →
    422; `LLMUnavailableError` → 503. (Mock at the router's import site, mirroring how the
    create/import endpoint tests mock the service.)
- **Frontend:**
  - `api.test.ts`: `extractIngredients` POSTs the text to `/recipes/extract-ingredients` and
    returns `lines`.
  - `AddRecipe.test.tsx`: clicking "Extract ingredients" calls `extractIngredients` with the
    textarea content and replaces the textarea with the returned lines; an extraction error
    surfaces via the error banner and leaves the textarea editable.

## Out of scope / non-goals

- Extracting the title or servings from the pasted text (only ingredients, per the request).
- A separate preview dialog (the textarea is the review surface).
- Changing the URL-import flow or the `POST /recipes` create endpoint.
- Bulk paste into an existing recipe (this is the new-recipe Add page only).
- Guaranteeing quantities — extracted ingredients often have none and will be flagged
  "Needs review" on the detail page, where the user adds amounts (and can add/delete rows).

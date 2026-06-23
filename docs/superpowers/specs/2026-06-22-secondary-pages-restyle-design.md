# Secondary pages restyle (Recipes list · Add recipe · Kroger setup) — design

Date: 2026-06-22

## Goal

Finish the UI overhaul with a lighter restyle + interaction polish of the three simpler
screens — **Recipes list**, **Add recipe**, and **Kroger setup** — on the already-shipped
visual foundation. This is increment 4 (final) of the UI overhaul
([2026-06-22-ux-ia-map-design.md](./2026-06-22-ux-ia-map-design.md)). No backend changes.

The earlier increments (foundation, grocery list, recipe detail) carried the heavy
restructuring; these three pages mostly need consistency with the foundation tokens/components
plus a few real interaction fixes (notably the fire-and-forget "Add to list" button and the
two-stacked-cards Add-recipe form).

## Background / current state

- `frontend/src/recipes/RecipeList.tsx`: `PageHeader` + an "Add recipe" `<Link>` styled as a
  button; `ErrorBanner`; a `<Input type="search">`; `Spinner`/`EmptyState`; then recipe
  `Card`s. Each card: title `<Link to={/recipes/:id}>`, a servings span, an **"Add to list"**
  `Button` calling `addRecipeToList(r.id)` **fire-and-forget (no feedback)**, and a 🗑 delete
  `Button variant="link"` (emoji) calling `remove(r)` (`window.confirm` → `deleteRecipe`).
  Client-side `filtered` by `query`.
- `frontend/src/recipes/AddRecipe.tsx`: **two stacked `Card`s shown at once** — an
  import-by-URL card (url `Input` + Import `Button` → `importRecipe`) and a manual card (Title
  `Input`, Servings number `Input`, Ingredients `<textarea>`, an "Extract ingredients"
  secondary `Button` → `extractIngredients(lines)` → `setLines(...)`, and a "Save recipe"
  `Button` → `createRecipe(title, servings, lines.split("\n"))`). State: `url/title/servings/
  lines/busy/error`; `run(action)` navigates on success; `extract()` handler.
- `frontend/src/recipes/KrogerSetup.tsx`: `PageHeader "Kroger"`; a connection `Card` showing
  "Connected…" text **or** a "Connect Kroger" `Button`; a "Home store" `Card` with a
  `selectedName` line, a zip `Input` + "Find stores" `Button`, and a `<ul>` of store rows with
  "Use this store" `Button`s. State: `status/zip/stores/selectedName/busy`; `connect()` →
  `getKrogerLoginUrl` → redirect; `findStores()` → `searchLocations`; `choose(loc)` →
  `setStore` → refresh `selectedName`.
- Shared primitives available: `SegmentedControl<T>({options, value, onChange})`
  (role=tablist/tab, aria-selected), `Pill`, `Button`, `Card`, `Input`, and `icons.tsx`
  (`TrashIcon`, etc.).

## Architecture

Three independent page reworks, each touching only its own file (+ its test). No new shared
components, no routes, no API/backend changes. All three reuse existing foundation primitives.

### Recipes list (`RecipeList.tsx`)

- **Sticky search:** wrap the search `Input` in a container that sticks under the page header
  while the card list scrolls (`sticky top-0 z-…` with the canvas background and a little
  vertical padding so cards don't bleed through). The "Add recipe" link-button stays in the
  header region. Search behavior (client-side `filtered`) is unchanged.
- **Add-to-list inline confirmation:** extract the per-card action into a small
  `AddToListButton({ recipeId, title })` component with local state `state: "idle" |
  "adding" | "added"`. On click → `state="adding"`, `await addRecipeToList(recipeId)`, then
  `state="added"` (button label "Added ✓", `disabled`) and a `setTimeout(~1500ms)` back to
  `"idle"`. On error → surface via the page-level `ErrorBanner` (lift an `onError(message)`
  callback into the component) and return to `"idle"`. Clear the timeout on unmount. Keep the
  `aria-label={`Add ${title} to list`}`.
- **Delete affordance:** replace the 🗑 emoji with `<TrashIcon aria-hidden />` inside the
  existing `Button variant="link"`; keep `aria-label={`Delete ${title}`}` and the
  `window.confirm` → `deleteRecipe` flow.
- Card layout, title link, servings span, empty/loading/error states all unchanged otherwise.

### Add recipe (`AddRecipe.tsx`)

- Add a **`SegmentedControl` [URL · Manual]** at the top, `mode: "url" | "manual"` defaulting
  to `"url"`. Render **only the active mode's fields**:
  - `url` mode: the url `Input` + Import `Button` (existing `importRecipe` logic).
  - `manual` mode: Title/Servings `Input`s, Ingredients `<textarea>` (keep `id="ingredients"`/
    `aria-describedby="ingredients-hint"`), the "Extract ingredients" `Button`, and the "Save
    recipe" `Button` (existing `extract()` / `createRecipe` logic).
- All existing state, `run()`, `extract()`, validation, error handling, and navigation-on-
  success are **unchanged** — only their visibility is gated by `mode`. The two `Card`
  wrappers collapse into the single active card.

### Kroger setup (`KrogerSetup.tsx`)

- **Connection state** becomes an explicit status line/`Pill` instead of plain text:
  - connected & not expired → `Pill tone="success"` "Connected ✓" (no button, or a subtle
    "Reconnect" link).
  - connected but expired → `Pill tone="warning"` "Session expired" + a **Reconnect**
    `Button` (calls `connect()`).
  - not connected → a **Connect Kroger** `Button` (calls `connect()`).
- **Home store** card: when a store is chosen, show "Home store: **{selectedName}**" clearly
  (heading-weight name); keep the zip `Input` + "Find stores" `Button` and the results `<ul>`
  with "Use this store" `Button`s below. Selection logic (`findStores`/`choose`/`setStore`)
  unchanged.
- No change to the OAuth redirect flow, status fetching, or store APIs.

## Data flow / errors

Unchanged from today on every page. `RecipeList` keeps its single page-level `ErrorBanner`;
the new `AddToListButton` reports failures up through an `onError` callback rather than owning
its own banner. `AddRecipe` and `KrogerSetup` keep their existing error state and banners.

## Testing

- `RecipeList.test.tsx`: clicking "Add to list" shows "Added ✓" and disables briefly, then
  resets (use fake timers); `addRecipeToList` called with the recipe id; an add failure
  surfaces the error banner; delete renders the `TrashIcon` button (assert by `aria-label`)
  and still confirms → `deleteRecipe`; search filters the list (unchanged).
- `AddRecipe.test.tsx`: defaults to URL mode (url field visible, manual fields hidden);
  toggling to Manual shows Title/Ingredients and hides the url field; Import calls
  `importRecipe`; Extract calls `extractIngredients` and fills the textarea; Save calls
  `createRecipe`.
- `KrogerSetup.test.tsx`: not-connected shows "Connect Kroger"; expired shows "Session
  expired" + "Reconnect"; connected shows "Connected ✓"; choosing a store shows "Home store:
  <name>".

## Scope / non-goals

- **No backend changes**; no new routes; no new shared components.
- No change to import/extract/create/connect/store logic — only layout, the segmented toggle,
  the inline add confirmation, and the trash icon.
- Visual tokens/components are already shipped (foundation increment); this is restyle +
  targeted interaction polish on top of them.

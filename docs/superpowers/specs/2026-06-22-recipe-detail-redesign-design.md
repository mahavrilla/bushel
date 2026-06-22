# Recipe-detail redesign (needs-review / tap-to-edit) — design

Date: 2026-06-22

## Goal

Make the Recipe-detail page scannable when a recipe has many ingredients: surface the rows
that **need review** at the top (open for editing), collapse the **reviewed** rows behind a
disclosure, and turn each row into a **tap-to-edit** summary so the list isn't a wall of
inputs. Increment 3 of the UI overhaul
([2026-06-22-ux-ia-map-design.md](./2026-06-22-ux-ia-map-design.md)), on the shipped visual
foundation.

## Background / current state

`frontend/src/recipes/RecipeDetail.tsx`: a header + intro + status line, then every
ingredient rendered as a `Row` `Card` that **always** shows all controls at once (raw text,
"Needs review" pill, a 🗑 delete, "Matched to" + a **Change** `IngredientPicker`, **Amount**/
**Unit** `Input`s, and a **Save** button), then an inline "Add an ingredient" form. The
`IngredientRead` shape: `id, raw_text, qty, unit, ingredient_id, ingredient_name,
parse_source, needs_review`. API used: `getRecipe`, `updateIngredient(recipeId, rowId,
{qty?,unit?,ingredient_id?})`, `deleteIngredient`, `addIngredient`. No backend changes are
needed.

## Architecture

Rework `RecipeDetail.tsx` only:
- Header (`PageHeader` title) + the existing `role="status"` line ("N item(s) need review" /
  "All items reviewed ✓"); replace the long intro paragraph with a short one-liner.
- Partition `recipe.ingredients` into `needsReview = ingredients.filter(i => i.needs_review)`
  and `reviewed = ingredients.filter(i => !i.needs_review)`.
- **Needs review** (only when `needsReview.length > 0`): render those `Row`s directly, each
  **open** by default (editor visible), with the amber flag treatment.
- **Reviewed** (only when `reviewed.length > 0`): a lightweight inline disclosure — a button
  "Reviewed · `<n>`" with a chevron that toggles the reviewed `Row` list. **Default open when
  `needsReview.length === 0`** (so an all-reviewed recipe shows its rows), otherwise collapsed.
  (A bespoke disclosure, not the bordered `CollapsibleSection`, to avoid nesting row cards
  inside a section card.)
- Inline **"Add an ingredient"** form at the bottom — unchanged.

## Row component (tap-to-edit)

`Row({ recipeId, ingredient, defaultOpen, onSaved })`:
- Local state: `open` (init `defaultOpen`), plus the existing `qty`, `unit`, `changing`,
  `error`.
- **Collapsed (`!open`):** a tappable summary `<button>` (full-width, ≥44px) that toggles
  `open` — shows `raw_text` (medium), a `Pill tone="warning"` "Needs review" when flagged, a
  muted second line `→ {ingredient_name ?? "—"}{qty != null ? ` · ${qty}${unit ? " " + unit
  : ""}` : ""}`, and a chevron. Accessible name includes the raw text (e.g. `aria-expanded`
  on the button).
- **Expanded (`open`):** the editor — "Matched to: {name}" + a **Change** button toggling the
  `IngredientPicker` (`onPick` → `updateIngredient(..., {ingredient_id})`), **Amount**/**Unit**
  `Input`s + **Save** (`updateIngredient(..., {qty, unit})`), and **Delete** (the existing
  `window.confirm` → `deleteIngredient`). The collapsed summary header remains tappable to
  collapse again.
- Card keeps the `needs_review ? "border-warning/40 bg-warning-tint"` flag treatment.
- All existing per-row error handling (`ErrorBanner`) stays.

`defaultOpen` is `ingredient.needs_review` (needs-review open, reviewed collapsed).

## Data flow / errors

Unchanged from today: the page holds `recipe`; each mutation (`updateIngredient`,
`deleteIngredient`, `addIngredient`) returns the updated `RecipeRead` and calls `setRecipe`.
Re-partitioning happens on each render, so saving a flagged row (which clears
`needs_review`) moves it into the Reviewed group on the next render. Errors via `ErrorBanner`.

## Testing

Rework `RecipeDetail.test.tsx` for collapsed/expanded behavior:
- A reviewed row shows its summary collapsed; tapping it reveals **Save**/**Change**/**Amount**;
  saving calls `updateIngredient(recipeId, rowId, {qty, unit})`.
- A needs-review row is open by default (editor visible without a tap).
- Re-map via the picker (tap to expand a reviewed row, or use a flagged row, → Change →
  pick → `updateIngredient({ingredient_id})`).
- Delete (expand → Delete → confirm → `deleteIngredient`); cancel does nothing.
- Add via the inline form (`addIngredient`); the status line count; the Reviewed disclosure
  toggles.

## Scope / non-goals

- No backend changes; no change to parsing/matching/add/delete endpoints.
- No sticky add bar (inline at bottom, per decision).
- The `IngredientPicker` is reused as-is.
- Visual tokens/components already done (foundation increment); this is structure + the
  tap-to-edit interaction on top of them.

# Grocery-list redesign (Items · Staples · Cart) — design

Date: 2026-06-22

## Goal

Rebuild the Grocery-list page from one long vertical scroll (Recipes + Shopping list +
Staples + Pantry + Send) into the **segmented Items · Staples · Cart** flow agreed in the
UX/IA map ([2026-06-22-ux-ia-map-design.md](./2026-06-22-ux-ia-map-design.md)), on the
already-shipped visual foundation. This is increment 2 of the UI overhaul.

Outcome: each view is short and focused, the cart action lives in its own tab (never buried),
pantry "already have it" folds into the item list, and the cart clearly shows the confirmed
line-up with their products.

## Background / current state

- `frontend/src/recipes/GroceryList.tsx` composes, top to bottom: a **Recipes** card
  (servings stepper + remove via `updateListServings` / `removeRecipeFromList`), a **Shopping
  list** card (consolidated `list.items`), then `<StaplesSection>`, `<PantryCheck>`,
  `<MatchAndSend>`.
- `getList()` → `GroceryListData { recipes: ListRecipe[], items: ListItem[] }`. `ListItem` has
  `ingredient_id, ingredient_name, category, quantities (SubQuantity[]), source_recipe_ids,
  pantry_status` — **no `item_id`**.
- Pantry: `set_decision(db, item_id, keep)` sets `pantry_status = "needed" if keep else
  "skipped"` for any item; `getPantry()` additionally flags recently-bought needed items as
  `maybe_have`.
- Match/cart: `getMatch()` → `MatchData { connected, store_location_id, items: MatchItem[] }`;
  each `MatchItem` has `item_id`, `ingredient_name`, `total_qty/unit`, `purchase_qty`,
  `purchase_qty_estimated`, `kroger_upc`, `current: ProductChoice | null`. Only kept (non-
  skipped) items appear. `searchItemProducts` / `confirmProduct` / `sendCart` and the
  `ProductPickerModal` already exist.

## Backend change (small)

Add `item_id` to the list items response so the Items tab can call the existing
`setPantryDecision`:
- `app/consolidate/schemas.py` `ListItemRead`: add `item_id: int`.
- `app/consolidate/router.py` `_serialize`: set `item_id=r.id` in the `ListItemRead(...)`
  (the `GroceryListItem` row `r` already has `.id`).
- Frontend `ListItem` type (`recipes/types.ts`): add `item_id: number`.

No other backend changes. ("Already have" on Items and "remove" on Cart both call
`setPantryDecision(item_id, false)`; undo calls `setPantryDecision(item_id, true)`.)

## New shared components (`components/ui/`)

- **`SegmentedControl`** — props `{ options: {value,label}[]; value; onChange }`. Renders an
  iOS-style segmented control (pill track, active segment raised). Each segment is a button
  with `role`/`aria-pressed` (or a radiogroup); 44px tall.
- **`CollapsibleSection`** — props `{ title; defaultOpen?; children }` (plus an optional
  summary/right slot). A titled header with a chevron that expands/collapses its body; sets
  `aria-expanded`. Used for the "On this list" recipes section and any future grouping.

Both get focused component tests.

## Page structure

`GroceryList.tsx` becomes the segmented shell:
- Loads the list (`getList`); if no recipes, the existing empty state.
- Holds `tab: "items" | "staples" | "cart"` state; renders the `SegmentedControl` + the
  active view. Default `items`.
- Decomposed into: `ItemsTab`, `StaplesSection` (reused as the Staples view), `CartTab`.
  `PantryCheck.tsx` is **removed** (its logic folds into `ItemsTab`).

### Items view (`recipes/ItemsTab.tsx`, new)
- Top: **`CollapsibleSection` "On this list · N recipes"** (collapsed by default) — each
  recipe row: title, servings input + Update (`updateListServings`), Remove
  (`removeRecipeFromList`). On change, refresh the list.
- Below: consolidated items **grouped by category** (items already arrive category-sorted;
  render a small uppercase category header when the category changes). Each item row:
  - name; consolidated amount via the existing `formatQuantities(item.quantities)` (this
    already shows multiple sub-amounts when units don't combine);
  - **source recipes**: map `item.source_recipe_ids` → titles from `list.recipes`; show "from
    `<A>`" or "from `<A> + <B>`", and "from N recipes" when more than two. (Per-recipe *amount*
    breakdown is out of scope — see non-goals.)
  - **"Already have"** action → `setPantryDecision(item.item_id, false)`; skipped items render
    greyed with an **Undo** (`setPantryDecision(item.item_id, true)`). Items whose
    `pantry_status === "maybe_have"` get a subtle "bought recently — already have?" hint.
  - Errors via `ErrorBanner`.

### Staples view
`StaplesSection` (restyled to the foundation; toggle staples on/off for the trip, add new).
Its `onChange` refreshes the parent list so item counts stay current.

### Cart view (`recipes/CartTab.tsx`, reworked from `MatchAndSend.tsx`)
- Loads `getMatch()`. Splits items into **Confirmed** (`current != null`) and **Needs a
  product** (`current == null`).
- Confirmed rows: ingredient, chosen product (`current.description` + size), buy qty, a ✓, and
  **Change** (opens `ProductPickerModal`). Needs-a-product rows: ingredient + **Choose
  product** (same modal). Picking confirms via `confirmProduct` and refreshes the match.
- Each row has a **remove** (trash, `aria-label="Remove <name>"`) → `setPantryDecision(item_id,
  false)` then `getMatch()` (drops it from the cart; stays on the recipe/list).
- A **fulfillment** selector (Pickup/Delivery) and a sticky **"Send to cart"** (`sendCart`),
  showing the post-send status summary. Keep the existing connect/store guards and the 409
  "reconnect" handling.

## Data flow & errors

- The shell owns the list fetch; `ItemsTab` receives `list` + an `onChange(list)` to update it
  after mutations. `StaplesSection` keeps its own fetch + `onChange` (refreshes the shell).
  `CartTab` owns its `getMatch` fetch and refetches after confirm/remove/send.
- Switching tabs renders the corresponding view. `CartTab` fetches `getMatch` on mount so it
  reflects the latest skip decisions. To avoid cross-tab staleness, the shell **re-fetches the
  list when the Items tab becomes active** (so a "remove" done on Cart, or a staple change, is
  reflected when you return to Items). Simple per-view fetching; no global store.
- All mutations surface failures via `ErrorBanner`, matching existing patterns.

## Testing

- `SegmentedControl.test`, `CollapsibleSection.test` — render, toggle, a11y attributes.
- `ItemsTab.test` — category grouping; multi-recipe "from …"; "Already have" calls
  `setPantryDecision(item_id, false)` and greys the row; Undo; recipe collapsible
  update/remove.
- `CartTab.test` — confirmed vs needs-a-product split; Change/Choose open the picker and
  confirm; remove calls `setPantryDecision(item_id, false)` + refetch; Send calls `sendCart`;
  409 → reconnect message.
- `GroceryList.test` — tab switching shows the right view; empty state.
- Backend: `test_consolidate_router` asserts the list items include `item_id`.
- Existing `MatchAndSend.test` / `PantryCheck.test` are replaced by `CartTab.test` /
  `ItemsTab.test`; `StaplesSection.test` stays.

## Scope / non-goals

- **Per-recipe amount breakdown** (e.g. "Turkey wraps 2 tbsp · Soup 1 tbsp") — deferred;
  consolidation stores only totals + `source_recipe_ids`, so amounts would need new backend
  computation. This increment shows source recipe **names** only.
- No new routes (segmented control is in-page state).
- No change to consolidation/matching logic, the product search, or staples behavior beyond
  restyle and the `item_id` field.
- Visual tokens/components are already done (foundation increment); this is structure +
  wiring on top of them.

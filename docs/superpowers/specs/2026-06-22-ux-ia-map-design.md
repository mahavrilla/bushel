# Bushel UX / information-architecture map — design

Date: 2026-06-22

## Purpose

A whole-app interaction map agreed during visual brainstorming, to guide the UI overhaul.
It defines the navigation model, the shared interaction patterns, and each page's structure
(what's grouped, what collapses, where the primary action lives). It is the **overarching
design**; it is implemented as a sequence of smaller specs+plans (see "Implementation
sequence"), starting from the visual foundation
([2026-06-22-ui-foundations-design.md](./2026-06-22-ui-foundations-design.md)).

**Locked visual direction:** "Clean & calm" on a cool neutral palette — white cards on
light gray, Inter typography, terracotta as the single accent, generous spacing, an iOS-style
bottom tab bar. Target: responsive web for mobile Safari (no PWA/native).

## Navigation model

- **Bottom tab bar** is the primary nav on mobile: **Recipes · List · Kroger**, each a small
  SVG line icon + label, active tab in terracotta, with safe-area bottom inset. On desktop
  (sm+), a horizontal header nav; bottom bar hidden.
- Routes are unchanged structurally: `/` Recipes, `/recipes/new` Add, `/recipes/:id` Detail,
  `/list` Grocery, `/kroger` Kroger. The Grocery list's internal flow becomes a **segmented
  control**, not new routes.

## Shared interaction patterns (the vocabulary)

These are the reusable behaviors used across pages. Each becomes a small shared primitive,
built when the first page needs it:

1. **Segmented control** — top-of-page tabs that swap focused views without scrolling (used
   by the Grocery list: Items / Staples / Cart).
2. **CollapsibleSection** — a titled section with a summary + chevron that expands/collapses
   (Recipe detail "Reviewed", per-recipe consolidation breakdown).
3. **Tap-to-edit row** — a compact row showing a summary; tapping reveals inline edit controls
   (Recipe-detail ingredient rows). Keeps long lists scannable.
4. **Sticky bottom action bar** — the screen's primary action pinned above the tab bar
   (Cart "Send to cart", Recipe-detail "Add an ingredient", Add-recipe "Save").
5. **Aisle grouping** — long item lists grouped by category header (Produce / Pantry / Meat…).
6. **Inline skip / remove** — a per-row action to exclude an item ("Already have" on Items;
   trash on Cart), with greyed state + Undo where it helps.

Minimum 44×44px touch targets; `:active` feedback; no horizontal scroll; safe-area insets.

## Per-page information architecture

### Recipes (`/`)
- Sticky **search** at top; scrollable list of **compact recipe cards** (title, servings,
  quick "Add to list", overflow for delete). Prominent **"Add recipe"** (header action or
  sticky). Empty state stays. Low complexity.

### Add recipe (`/recipes/new`)
- Two clear modes: **Import by URL** and **Manual** (title, servings, the paste/extract
  ingredients box). Primary action ("Import" / "Save recipe") uses the sticky-action pattern.
  Low complexity — mostly restyle.

### Recipe detail (`/recipes/:id`)
- Header: title + count ("8 ingredients · 2 need review").
- **"Needs review · N"** section surfaced at top (amber dot). Rows are **tap-to-edit**:
  collapsed they show raw text → matched ingredient + a flag; tapping expands amount/unit +
  matched-ingredient picker + Delete · Save.
- **"Reviewed · N"** is a **CollapsibleSection** (collapsed by default) to cut the scroll.
- **"Add an ingredient"** pinned at the bottom (sticky action). Densest screen by nature;
  this structure keeps attention on what needs fixing.

### Grocery list (`/list`) — segmented: **Items · Staples · Cart**
Pantry "check" folds into Items (no separate step). The segmented control keeps each view
short and puts the cart one tap away.

- **Items** — the **consolidated** shopping list (one row per ingredient, amounts summed
  across recipes), **grouped by aisle**. Each row shows the need/buy amount and a subtle
  "from `<recipe(s)>`". Multi-recipe items show **"from N recipes"** and expand
  (CollapsibleSection) to a per-recipe breakdown. When units can't be combined (e.g. cloves +
  tablespoons), show each sub-amount separately with a small note (mirrors the backend's
  existing consolidation, which keeps incompatible units as separate sub-quantities).
  Every row has **"Already have"** → marks it skipped (greyed + Undo) so it is **excluded
  from the Cart** (this is the pantry pass, inline).
- **Staples** — toggle the user's saved staples on/off for this trip; add a new staple inline.
- **Cart** (review & send) — the **confirmed line-up**: each kept item shows its chosen
  product, buy qty, a ✓, and **Change**. Items without a product are grouped under **"Needs a
  product"** with a "Choose product" action (opens the product picker). Every line has a
  **trash control to remove it from this send** (excluded from the cart this trip; it stays on
  the recipe/list). A **fulfillment** selector (Pickup/Delivery) and a sticky **"Send to
  cart"** button. After send, a status summary.

### Kroger setup (`/kroger`)
- Connect Kroger account + pick home store (search by zip). Simple; restyle + clearer states
  (connected / disconnected / store selected). Low complexity.

## Mapping to current code (informs implementation)

- The Grocery list page (`GroceryList.tsx`) currently stacks list + `StaplesSection` +
  `PantryCheck` + `MatchAndSend` vertically. The new IA splits these across the **Items /
  Staples / Cart** segments: Items = consolidated list + inline pantry skip (folds in
  `PantryCheck`), Staples = `StaplesSection`, Cart = `MatchAndSend` reworked into the
  confirmed/needs-a-product layout with per-line remove + "Send to cart". No new routes.
- `RecipeDetail.tsx` gains the needs-review/reviewed grouping, collapsible reviewed section,
  and tap-to-edit rows (today every row shows all fields at once).
- The product picker modal already exists and is reused from the Cart's "Change"/"Choose
  product".

## Implementation sequence (each its own spec → plan → build)

1. **Foundations** (already specced): tokens, typography, spacing, restyled shared
   components, the mobile shell + bottom nav + safe areas + nav/util icons. Restyles every
   page at once. *Build first.*
2. **Grocery list** redesign (Items · Staples · Cart) — highest value; introduces the
   SegmentedControl, CollapsibleSection, sticky ActionBar, aisle grouping, consolidation
   breakdown, inline skip, and per-line remove primitives.
3. **Recipe detail** redesign — needs-review grouping, collapsible reviewed, tap-to-edit rows.
4. **Recipes list / Add recipe / Kroger setup** — lighter restyle + sticky actions (can be
   one combined increment).

Each increment keeps behavior/tests green and is shippable on its own.

## Scope / non-goals

- This map defines structure and interaction, not pixel-level visuals (that's foundations).
- No new product features or backend/data changes beyond what the IA implies (e.g. the
  per-line "remove from send" reuses the existing skip/keep mechanism; consolidation detail
  reads existing `source_recipe_ids` / `quantities`).
- No PWA (manifest/offline) or native app.
- Per-page redesigns are separate specs; this document is the shared reference they follow.

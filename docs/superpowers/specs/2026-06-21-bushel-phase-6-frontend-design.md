# Bushel — Phase 6: Frontend Polish (design)

**Date:** 2026-06-21
**Status:** approved (pre-implementation)
**Depends on:** Phases 2–4 (the screens being polished already exist).
**Note:** Built **before** Phase 5 (Matching & pantry) at the user's request. Phase 5's future
screens will be styled with the system this phase establishes.

## Goal

Turn Bushel's functional-but-unstyled web UI into a cohesive, pleasant, mobile-friendly app:
a real visual design (the "Warm Pantry" system), a redesigned app shell with client-side
routing, and proper loading / error / empty states across every screen. **Frontend-only — no
backend or API changes.**

## Scope (from brainstorming)

In scope, all four chosen:
1. **Visual restyle** of every existing screen using **Tailwind CSS** + the Warm Pantry theme.
2. **Loading / error / empty states** everywhere (spinners, error banners, empty states).
3. **Mobile-responsive layout** (usable on a phone while shopping).
4. **Client-side routing** (`react-router-dom`) + a redesigned **app shell** (header nav + bottom
   tab bar) with a simplified 3-destination navigation.

Out of scope: backend/API changes, new features, Phase 5 matching/pantry logic, the deferred
"state issues" noted during Phase 4 smoke testing.

## Visual direction — "Warm Pantry"

A cozy kitchen aesthetic: cream background, terracotta primary, a warm serif for headings.
Approved via mockups (saved in `.superpowers/brainstorm/`).

**Palette (Tailwind theme tokens):**

| Token | Hex | Use |
|---|---|---|
| `cream` | `#FBF7EF` | app background |
| `surface` | `#FFFDF8` | cards |
| `primary` / `primary-hover` | `#C2410C` / `#9A3412` | primary actions (terracotta) |
| `accent` | `#D97706` | amber accent |
| `success` | `#4D7C0F` | in-stock green |
| `danger` | `#B91C1C` | errors / out-of-stock |
| `ink` | `#44403C` | body text |
| `heading` | `#7C2D12` | headings |
| `muted` | `#A8A29E` | secondary text |
| `line` | `#ECDFC9` | borders |
| `tint-amber` | `#FEF3E2` | warning tint bg |
| `tint-green` | `#ECFCCB` | success tint bg |

**Typography:** headings = **Fraunces** (serif); body = **Inter** (sans) — loaded via Google
Fonts `@import` in `index.css`, with `Georgia`/`system-ui` fallbacks.

**Status pills:** in-stock `bg-tint-green text-success` · out-of-stock `bg-red-100 text-danger` ·
check-quantity `bg-tint-amber text-primary` · buy-in-person `bg-stone-100 text-stone-600`.

## Architecture

**New tooling (frontend only):**
- **Tailwind CSS** + `postcss` + `autoprefixer`, configured into Vite. `tailwind.config.js` holds
  the theme tokens above (`theme.extend.colors`, `fontFamily.heading`/`sans`, `borderRadius.xl`).
  `index.css` has `@tailwind base/components/utilities` + the font `@import`; imported once in
  `main.tsx`. Body defaults: `bg-cream text-ink font-sans`.
- **`react-router-dom`** for routes; replaces the current `useState` view-switching in `App.tsx`.

**File structure:**
```
frontend/src/
  main.tsx                 # <BrowserRouter><App/></BrowserRouter>; import index.css
  index.css                # @tailwind directives + Fraunces/Inter import + base body styles
  App.tsx                  # <Routes> within the AppShell layout route
  components/
    AppShell.tsx           # header nav (desktop) + bottom tab bar (mobile) + page container + <Outlet/>
    ui/
      Button.tsx  Card.tsx  Input.tsx  Pill.tsx
      Spinner.tsx  EmptyState.tsx  ErrorBanner.tsx  PageHeader.tsx
  test/
    renderWithRouter.tsx   # test helper: render a screen wrapped in <MemoryRouter>
  recipes/                 # existing screens, restyled in place
    RecipeList.tsx  AddRecipe.tsx  RecipeDetail.tsx
    GroceryList.tsx  KrogerSetup.tsx  MatchAndSend.tsx  (MatchReview.tsx renamed/absorbed)
  api.ts                   # UNCHANGED
```

Each `ui/` primitive is small, focused, and presentational (no data fetching).

## Routing & navigation

**Three destinations** in the nav (simplified from five buttons):

| Route | Screen | Nav? |
|---|---|---|
| `/` | Recipes (list) | ✅ Recipes |
| `/recipes/new` | Add recipe | — (button on `/`) |
| `/recipes/:id` | Recipe detail | — |
| `/list` | Grocery list **+ Match & send** | ✅ List |
| `/kroger` | Kroger setup | ✅ Kroger |

`AppShell` is the layout route wrapping all of the above via `<Outlet/>`:
- **Header** (all sizes): Fraunces "🧺 Bushel" brand; on `sm+`, horizontal `NavLink`s for the 3
  destinations with active highlighting (terracotta).
- **Bottom tab bar** (`<sm` only): sticky, 3 icon+label tabs (Recipes / List / Kroger).
- **Page container**: centered `max-w`, padded, `bg-cream`.

"Add recipe" is a `PageHeader` action on `/` that routes to `/recipes/new`; "Match & send" is a
panel on `/list`, not a top-level tab.

## UI primitives (`components/ui/`)

- **`Button`** — `variant: "primary" | "secondary" | "link"`, `disabled`, `loading` (spinner +
  disabled).
- **`Card`** — surface bg, `border-line`, `rounded-xl`, padding.
- **`Input`** — labeled input; the `<label>` wraps the field so `getByLabelText` still works; focus
  ring in primary.
- **`Pill`** — `tone: "success" | "danger" | "warning" | "neutral"` → the status badges.
- **`Spinner`** — terracotta ring; `size: "sm" | "md"`.
- **`EmptyState`** — icon + message + optional action button.
- **`ErrorBanner`** — `role="alert"`, danger-tinted; optional action (e.g. reauth "Reconnect").
- **`PageHeader`** — Fraunces page title + optional right-aligned action slot.

## Per-screen changes

Every screen composes the primitives and gains **loading** (Spinner), **error** (ErrorBanner),
and **empty** (EmptyState) treatments. No behavior/endpoint changes.

- **Recipes (`/`)** — `PageHeader` "Recipes" + "+ Add recipe" → `/recipes/new`; recipes as Cards;
  empty → "No recipes yet" with an add action; row click → `/recipes/:id`.
- **Add recipe (`/recipes/new`)** — Input/Button form (URL import + manual entry); submit loading;
  error banner on failure; on success → `/recipes/:id`.
- **Recipe detail (`/recipes/:id`)** — styled ingredient list; `needs_review`/parse-source as
  Pills; "Add to list" Button.
- **Grocery list (`/list`)** — the consolidated list in category-grouped Cards, **then a
  `MatchAndSend` panel** (the former `MatchReview`, restyled): per-item product search with
  price/stock Pills, "Choose", `purchase_qty` with a "check quantity" Pill, modality select,
  primary "Send to Kroger cart", per-item results, and the reauth `ErrorBanner`. Empty list →
  empty state. Calls the same `getList` / `getMatch` / `searchItemProducts` / `confirmProduct` /
  `sendCart` endpoints — purely a presentation merge.
- **Kroger (`/kroger`)** — connection-status Card, zip Input → stores as selectable Cards,
  selected-store confirmation; loading/error states.

`MatchReview.tsx` is renamed/absorbed into `MatchAndSend.tsx`, composed into `/list`.

## Testing

Presentation-only, so existing behavior tests stay meaningful — they need a router wrapper and
updated nav queries. Still **vitest + Testing Library** (no new framework).

- **`renderWithRouter` helper** wraps screens in `<MemoryRouter>` (with `initialEntries` where a
  route param matters).
- **UI primitives** — one focused test each: renders, variant classes applied, `disabled`/`loading`
  disables + shows Spinner, action callbacks fire, `ErrorBanner` has `role="alert"`, `EmptyState`
  action routes.
- **`AppShell`** — renders the 3 nav destinations, highlights the active one, shows the bottom tab
  bar markup.
- **Updated existing tests** — `App.test` asserts routing to `/`, `/list`, `/kroger` (instead of
  `useState` buttons); the `MatchReview` reauth-`alert` test moves to `MatchAndSend`;
  `KrogerSetup` / `MatchAndSend` / `GroceryList` keep their behavior assertions, wrapped in the
  router. Accessible queries (`getByRole` / `getByLabelText` / `getByText`) are preserved (Tailwind
  classes don't affect them).
- **Build/type check** — `npm run build` (tsc + vite) stays green; Tailwind `content` globs
  verified so classes aren't purged.

## Out of scope / deferred

- Backend or API changes (none).
- Phase 5 matching/pantry logic (styled later with this system).
- The Phase-4 smoke-test "state issues" (handled separately when revisited).

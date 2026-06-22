# UI foundations — design language + mobile shell — design

Date: 2026-06-22

## Goal

Refresh Bushel's visual foundation to be cleaner, clearer, and comfortable on a phone
(mobile Safari / iOS), by updating the shared design layer — color tokens, typography,
spacing, the reusable UI components, and the app shell/navigation. Because every page is
built from these shared pieces, this single pass restyles the whole app at once.

This is the **first** of a multi-spec UI effort. Per-page layout redesigns (Recipes, Add
recipe, Recipe detail, Grocery list, Kroger setup) are **separate, later specs** that build
on this foundation. This spec changes look-and-feel and the shell only — not page-level
information architecture or features.

**Chosen direction (from visual brainstorming):** "Clean & calm" on a **cool neutral**
palette — white cards on light gray, Inter typography, terracotta as the single accent,
generous spacing, an iOS-style bottom tab bar.

## Background / current state

- **Tokens** live in `frontend/tailwind.config.js` (warm palette: `cream`, `surface`,
  `primary` terracotta, `accent`, `heading` brown, `ink`, `muted`, `line`, `tint-*`) and
  `frontend/src/index.css` (imports Fraunces + Inter; `body` uses cream/ink; `h1–h3` use
  Fraunces serif in the brown `heading` color).
- **Shared components** in `frontend/src/components/ui/`: `Button` (variants
  `primary`/`secondary`/`link`), `Card`, `Pill` (tones success/danger/warning/neutral),
  `Input`, `EmptyState`, `ErrorBanner`, `Spinner`, `PageHeader`, `Modal`.
- **Shell** `frontend/src/components/AppShell.tsx`: top header with "🧺 Bushel" wordmark +
  horizontal nav (sm+), and a fixed bottom nav (sm:hidden) — both use emoji icons and the
  tabs Recipes (`/`), List (`/list`), Kroger (`/kroger`).
- `frontend/index.html` holds the `<meta viewport>` and page title.
- Pages compose these components; many tests assert text/roles (e.g. "Bushel", nav link
  names, button names) — restyling must preserve those.

## New design tokens

Replace the palette in `tailwind.config.js` `theme.extend.colors` and update `index.css`.

| Token | Value | Use |
|---|---|---|
| `canvas` | `#F6F7F9` | app background |
| `surface` | `#FFFFFF` | cards, sheets, nav bar |
| `line` | `#ECECEF` | hairline borders, dividers |
| `line-strong` | `#E5E7EB` | input borders |
| `heading` | `#1F2937` | titles / strong text |
| `ink` | `#374151` | body text |
| `muted` | `#6B7280` | secondary/meta text |
| `primary` (DEFAULT/hover) | `#C2410C` / `#9A3412` | brand accent, primary buttons |
| `primary-tint` | `#FBEAE0` | soft accent backgrounds |
| `warning` (DEFAULT/tint) | `#B45309` / `#FEF3C7` | "Check quantity" etc. |
| `danger` (DEFAULT/tint) | `#B91C1C` / `#FEE2E2` | errors, out of stock |
| `success` (DEFAULT/tint) | `#15803D` / `#DCFCE7` | reviewed / in stock |

Remove `cream`, `accent`, `tint-amber`, `tint-green` (migrate their usages to the new
tokens). `index.css`: `body` → `bg-canvas text-ink`; drop the Fraunces `@import` and the
`h1–h3` serif rule (headings inherit Inter).

## Typography

- **Inter only** (400/500/600/700); remove Fraunces entirely. `font-heading` is dropped;
  headings use Inter via weight/size, not a separate family.
- Scale (defaults; components apply them): page title ~22px/700 with tight tracking
  (`tracking-tight`); section/card title 16–17px/600; body 14px; meta/caption 12–13px.
  Comfortable line-heights.

## Spacing, shape, touch targets

- Card radius 14px (`rounded-2xl`-ish — keep a `xl: 0.75rem` plus add a `2xl: 1rem`),
  button/input radius 10px. 16px screen padding, 12px gaps between cards.
- **Minimum 44×44px touch targets** (Apple HIG): buttons are ≥44px tall (≥`py-3`); tappable
  rows/controls sized accordingly. Use `:active` feedback (not hover-only).

## Mobile shell (responsive web for iOS Safari)

`AppShell.tsx` + `index.html`:
- **Bottom tab bar** (primary nav on mobile): Recipes / List / Kroger, each a small **SVG
  line icon** + label; active tab in `primary`, inactive in `muted`. Fixed to the bottom,
  `surface` background with a top hairline, and bottom padding using
  `env(safe-area-inset-bottom)` so it clears the iPhone home indicator.
- **Header**: keep the "Bushel" wordmark (Inter, semibold) + a small brand mark; on desktop
  (sm+) keep the horizontal nav, hide the bottom bar. Apply `safe-area-inset-top`.
- `index.html`: viewport `width=device-width, initial-scale=1, viewport-fit=cover`. Ensure
  no horizontal scroll; main content centered with a max width (e.g. `max-w-md`/`max-w-2xl`)
  and 16px gutters.
- Add a small **icon set**: a new `components/ui/icons.tsx` (or `Icon`) exporting simple
  inline SVG line icons for the three nav destinations (book/recipes, basket/list,
  cart/kroger), plus a couple reused glyphs (close ✕, trash, search) so we stop relying on
  emoji where it matters for the "clean" look.

## Components restyled

Restyle in place (same props/exports — only classes/markup change) so pages keep working:
- **Button**: `primary` = filled terracotta (`bg-primary text-white`, hover `primary-hover`);
  `secondary` = `bg-surface` + `line` border + `heading` text; `link` = `primary` text.
  All ≥44px tall, radius 10, clear `:active`/disabled states. (No new variants.)
- **Card**: `surface` bg, `line` hairline border, radius 14, subtle shadow (`0 1px 2px
  rgba(16,24,40,.04)`), comfortable padding.
- **Pill** (status tags): map tones to the new tints — warning `#FEF3C7/#B45309`, danger
  `#FEE2E2/#B91C1C`, success `#DCFCE7/#15803D`, neutral `#F1F3F5/#475569`.
- **Input/textarea**: `surface` bg, `line-strong` border, radius 10, `primary` focus ring,
  ≥44px tall; labels in `heading`, hints in `muted`.
- **EmptyState / ErrorBanner / Spinner / PageHeader / Modal**: re-skin to the new tokens
  (Modal already exists; just tokens + safe spacing). PageHeader title uses the new title
  scale.
- The Modal close, list delete, and search affordances use the new SVG icons where they
  currently use emoji (✕, 🗑, 🔍), keeping `aria-label`s.

## Scope / non-goals

- **In scope:** tokens, typography, spacing/shape, the shared UI components, the app
  shell + bottom nav + safe areas + nav/util icons, viewport meta.
- **Out of scope (later specs):** per-page layout/IA redesigns; any new features; PWA
  (manifest/service worker/offline) or native app; data/behavior changes.

## Testing

- This is largely a visual/className change; **behavior tests must stay green**. Run the
  full frontend suite + `tsc` + build.
- Update only the tests that assert presentation that genuinely changes: e.g. if a nav item
  or the Modal close switches from emoji to an SVG, keep the same accessible name/`aria-label`
  so role/name queries still pass; adjust any test that asserts an emoji string or the
  Fraunces/`font-heading` class directly.
- Component tests (`components/ui/*.test.tsx`, `AppShell.test.tsx`) updated where they assert
  removed tokens/classes; otherwise they validate the components still render with the same
  API. No backend changes.

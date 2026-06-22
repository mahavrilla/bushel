# UI foundations (design language + mobile shell) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle Bushel's shared layer — design tokens, typography, the reusable UI components, and the mobile app shell — to the "clean & calm, cool neutral" direction, restyling every page at once without changing behavior.

**Architecture:** Change the Tailwind tokens + `index.css` (cool palette, Inter-only), restyle the shared `components/ui/*` and the `AppShell` (iOS-style bottom tab bar with SVG icons + safe-area insets), and migrate the few stray usages of removed tokens. No page-level layout/IA changes (those are later increments). This is mostly className/markup work, so each task makes its change and **keeps the full test suite + typecheck + build green**; new structure (icons, shell) gets targeted tests.

**Tech Stack:** React + TypeScript + Vite + Tailwind (frontend, vitest + Testing Library).

---

## Conventions

```bash
cd frontend && npm test            # full suite
cd frontend && npm test -- <path>  # one file
cd frontend && npx tsc -b          # typecheck
cd frontend && npm run build       # production build
```

There are no backend changes. The bar for every task: the change is made, `npm test`, `tsc -b`, and `npm run build` all pass.

---

## File Structure

- Modify `frontend/tailwind.config.js` — new color tokens, Inter-only fonts, radius scale.
- Modify `frontend/src/index.css` — drop Fraunces, `body` → canvas; remove serif heading rule.
- Modify `frontend/index.html` — `viewport-fit=cover`.
- Create `frontend/src/components/ui/icons.tsx` (+ test) — SVG icon set.
- Modify shared components: `Button`, `Card`, `Pill`, `Input`, `Spinner`, `EmptyState`,
  `ErrorBanner`, `PageHeader`, `Modal` in `frontend/src/components/ui/`.
- Modify `frontend/src/components/AppShell.tsx` — header + mobile bottom tab bar.
- Migrate removed-token usages in `frontend/src/recipes/PantryCheck.tsx`,
  `RecipeDetail.tsx`, `MatchAndSend.tsx`.

**Token migration map** (removed → new): `cream` → `canvas`; `accent` → `warning`;
`tint-amber` → `warning-tint`; `tint-green` → `success-tint`; the `font-heading` family is
removed (headings use Inter). Heavily-used names `surface`, `line`, `heading`, `ink`,
`muted`, `primary`/`primary-hover` keep their names with **new values**, so ~90 usages update
for free.

**Scope note:** foundations swaps emoji → SVG only for the **nav** and the **Modal close**.
Per-row emoji in pages (🗑 in lists, 🔍) are swapped during those pages' later redesigns.

---

## Task 1: Design tokens, base CSS, viewport

**Files:**
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/index.css`
- Modify: `frontend/index.html`

- [ ] **Step 1: Replace the Tailwind theme**

Replace `frontend/tailwind.config.js` with:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F6F7F9",
        surface: "#FFFFFF",
        line: "#ECECEF",
        "line-strong": "#E5E7EB",
        heading: "#1F2937",
        ink: "#374151",
        muted: "#6B7280",
        primary: { DEFAULT: "#C2410C", hover: "#9A3412", tint: "#FBEAE0" },
        warning: { DEFAULT: "#B45309", tint: "#FEF3C7" },
        danger: { DEFAULT: "#B91C1C", tint: "#FEE2E2" },
        success: { DEFAULT: "#15803D", tint: "#DCFCE7" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        lg: "0.625rem", // 10px — buttons, inputs
        xl: "0.75rem", // 12px — kept for existing usages
        "2xl": "0.875rem", // 14px — cards
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 2: Update base CSS**

Replace `frontend/src/index.css` with:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-canvas text-ink font-sans antialiased;
  }
}
```

(Drops the Fraunces import and the serif `h1–h3` rule; headings now use Inter and components
set their own size/color.)

- [ ] **Step 3: Viewport for safe areas**

In `frontend/index.html`, replace the viewport meta line with:

```html
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

- [ ] **Step 4: Verify build + suite**

```bash
cd frontend && npx tsc -b && npm run build && npm test 2>&1 | tail -3
```
Expected: build succeeds; tests pass. (Components still reference `surface`/`line`/etc. which
now resolve to new values; the few removed-token usages are fixed in Task 2 — they render as
unstyled until then but don't fail the build or tests.)

- [ ] **Step 5: Commit**

```bash
git add frontend/tailwind.config.js frontend/src/index.css frontend/index.html
git commit -m "feat(ui): cool-neutral tokens, Inter-only, viewport-fit cover"
```

---

## Task 2: Migrate removed-token usages

**Files:**
- Modify: `frontend/src/recipes/PantryCheck.tsx`
- Modify: `frontend/src/recipes/RecipeDetail.tsx`
- Modify: `frontend/src/recipes/MatchAndSend.tsx`

(Button/Pill/AppShell also reference removed tokens but are rewritten in later tasks.)

- [ ] **Step 1: Retoken the three page files**

- `PantryCheck.tsx` line ~42: change `bg-tint-amber` → `bg-warning-tint`.
- `RecipeDetail.tsx` line ~64: change the row className from
  `ingredient.needs_review ? "border-accent bg-tint-amber" : ""` to
  `ingredient.needs_review ? "border-warning/40 bg-warning-tint" : ""`.
- `MatchAndSend.tsx` line ~115: change `bg-cream` → `bg-canvas`.

- [ ] **Step 2: Confirm no removed tokens remain anywhere except files rewritten later**

```bash
cd frontend && grep -rnE "tint-amber|tint-green|bg-cream|border-accent|text-accent|font-heading" src
```
Expected: only matches left are in `components/ui/Button.tsx`, `components/ui/Pill.tsx`, and
`components/AppShell.tsx` (rewritten in Tasks 4 and 6). No matches in `recipes/` or `index.css`.

- [ ] **Step 3: Verify**

```bash
cd frontend && npx tsc -b && npm test 2>&1 | tail -3
```
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/recipes/PantryCheck.tsx frontend/src/recipes/RecipeDetail.tsx frontend/src/recipes/MatchAndSend.tsx
git commit -m "refactor(ui): migrate page files off removed tokens"
```

---

## Task 3: SVG icon set

**Files:**
- Create: `frontend/src/components/ui/icons.tsx`
- Test: `frontend/src/components/ui/icons.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/ui/icons.test.tsx`:

```tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BasketIcon, BookIcon, CartIcon, CloseIcon } from "./icons";

describe("icons", () => {
  it("render as decorative svgs with the given size", () => {
    const { container } = render(
      <div>
        <BookIcon />
        <BasketIcon />
        <CartIcon />
        <CloseIcon />
      </div>,
    );
    const svgs = container.querySelectorAll("svg");
    expect(svgs).toHaveLength(4);
    svgs.forEach((svg) => {
      expect(svg).toHaveAttribute("aria-hidden", "true");
      expect(svg).toHaveAttribute("width", "24");
    });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- src/components/ui/icons.test.tsx
```
Expected: FAIL (module missing).

- [ ] **Step 3: Create the icons**

Create `frontend/src/components/ui/icons.tsx`:

```tsx
import type { SVGProps } from "react";

function Svg({ size = 24, children, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export type IconProps = SVGProps<SVGSVGElement> & { size?: number };

export const BookIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2V5Z" />
    <path d="M18 17H6" />
  </Svg>
);

export const BasketIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 9h14l-1.2 9.2A2 2 0 0 1 15.8 20H8.2a2 2 0 0 1-2-1.8L5 9Z" />
    <path d="M9 9 12 4l3 5" />
  </Svg>
);

export const CartIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="9" cy="20" r="1" />
    <circle cx="18" cy="20" r="1" />
    <path d="M3 4h2l2.2 11.2A2 2 0 0 0 9.2 17h7.6a2 2 0 0 0 2-1.6L20 8H6" />
  </Svg>
);

export const CloseIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd frontend && npm test -- src/components/ui/icons.test.tsx && npx tsc -b
```
Expected: PASS, clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/icons.tsx frontend/src/components/ui/icons.test.tsx
git commit -m "feat(ui): SVG icon set (nav + close)"
```

---

## Task 4: Restyle Button, Card, Pill, Input, Spinner

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx`, `Card.tsx`, `Pill.tsx`, `Input.tsx`, `Spinner.tsx`

- [ ] **Step 1: Restyle the components**

`Button.tsx` — replace the `variants` map and the className (primary filled, secondary
white+hairline, link terracotta; ≥44px tall, radius 10):

```tsx
import type { ButtonHTMLAttributes } from "react";

import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "link";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-white hover:bg-primary-hover active:bg-primary-hover",
  secondary: "border border-line bg-surface text-heading hover:bg-canvas active:bg-canvas",
  link: "text-primary underline hover:text-primary-hover px-1",
};

export function Button({
  variant = "primary",
  loading = false,
  disabled,
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const sizing = variant === "link" ? "" : "min-h-[44px] px-4 py-2.5";
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 ${sizing} ${variants[variant]} ${className}`}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}
```

`Card.tsx`:

```tsx
export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-line bg-surface p-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)] ${className}`}
    >
      {children}
    </div>
  );
}
```

`Pill.tsx`:

```tsx
type Tone = "success" | "danger" | "warning" | "neutral";

const tones: Record<Tone, string> = {
  success: "bg-success-tint text-success",
  danger: "bg-danger-tint text-danger",
  warning: "bg-warning-tint text-warning",
  neutral: "bg-canvas text-muted",
};

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
```

`Input.tsx` (radius 10, line-strong border, ≥44px, primary focus ring):

```tsx
import type { InputHTMLAttributes } from "react";

export function Input({
  label,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-ink">
      <span className="font-medium text-heading">{label}</span>
      <input
        className={`min-h-[44px] rounded-lg border border-line-strong bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary ${className}`}
        {...props}
      />
    </label>
  );
}
```

`Spinner.tsx` (border uses new tokens — `border-line`/`border-t-primary` keep working):

```tsx
export function Spinner({ size = "md" }: { size?: "sm" | "md" }) {
  const dim = size === "sm" ? "h-4 w-4 border-2" : "h-6 w-6 border-[3px]";
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-line border-t-primary ${dim}`}
    />
  );
}
```

(Spinner is unchanged in markup; included for completeness — only its tokens' values changed.)

- [ ] **Step 2: Verify the component + dependent tests**

```bash
cd frontend && npm test -- src/components/ui && npm test 2>&1 | tail -3 && npx tsc -b
```
Expected: pass. If `Pill.test`/`Button.test` assert old class strings, update those assertions
to the new classes (keep behavioral assertions intact).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/Button.tsx frontend/src/components/ui/Card.tsx frontend/src/components/ui/Pill.tsx frontend/src/components/ui/Input.tsx frontend/src/components/ui/Spinner.tsx
git commit -m "feat(ui): restyle Button/Card/Pill/Input to cool-neutral + 44px targets"
```

---

## Task 5: Restyle EmptyState, ErrorBanner, PageHeader, Modal

**Files:**
- Modify: `frontend/src/components/ui/EmptyState.tsx`, `ErrorBanner.tsx`, `PageHeader.tsx`, `Modal.tsx`

- [ ] **Step 1: Restyle**

`PageHeader.tsx` (title uses the page-title scale):

```tsx
export function PageHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center gap-3">
      <h2 className="text-[22px] font-bold tracking-tight text-heading">{title}</h2>
      {action && <div className="ml-auto">{action}</div>}
    </div>
  );
}
```

`EmptyState.tsx` (token-only refresh; keep the `icon`/`actionLabel`/`onAction` API):

```tsx
import { Button } from "./Button";

export function EmptyState({
  icon,
  message,
  actionLabel,
  onAction,
}: {
  icon?: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface p-10 text-center">
      {icon && <div className="mb-2 text-3xl">{icon}</div>}
      <p className="text-muted">{message}</p>
      {actionLabel && onAction && (
        <div className="mt-4">
          <Button onClick={onAction}>{actionLabel}</Button>
        </div>
      )}
    </div>
  );
}
```

`ErrorBanner.tsx` (danger tint + token):

```tsx
import { Button } from "./Button";

export function ErrorBanner({
  message,
  actionLabel,
  onAction,
}: {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div
      role="alert"
      className="mb-4 flex items-center gap-3 rounded-lg border border-danger/20 bg-danger-tint px-4 py-3 text-sm text-danger"
    >
      <span>{message}</span>
      {actionLabel && onAction && (
        <Button variant="link" className="ml-auto" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
```

`Modal.tsx` — keep the existing structure/behavior; swap the ✕ glyph for `CloseIcon`
(keep `aria-label="Close"`), and refresh tokens. Replace the close `<button>` content and add
the import `import { CloseIcon } from "./icons";`:

```tsx
          <button
            type="button"
            aria-label="Close"
            className="ml-auto flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-heading"
            onClick={onClose}
          >
            <CloseIcon size={18} />
          </button>
```

(Leave the rest of `Modal.tsx` — overlay, Escape handler, `role="dialog"` — unchanged.)

- [ ] **Step 2: Verify**

```bash
cd frontend && npm test 2>&1 | tail -3 && npx tsc -b
```
Expected: pass. `Modal.test` queries the close button by `aria-label`/role "Close", which is
preserved, so it still passes.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/EmptyState.tsx frontend/src/components/ui/ErrorBanner.tsx frontend/src/components/ui/PageHeader.tsx frontend/src/components/ui/Modal.tsx
git commit -m "feat(ui): restyle EmptyState/ErrorBanner/PageHeader/Modal; SVG close"
```

---

## Task 6: App shell + mobile bottom tab bar

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/components/AppShell.test.tsx` (existing — must keep passing)

- [ ] **Step 1: Rewrite AppShell**

Replace `frontend/src/components/AppShell.tsx` with (keeps `NavLink` + the labels Recipes /
List / Kroger and their hrefs so `AppShell.test` and `App.test` pass; adds SVG icons,
safe-area insets, a bottom tab bar, centered max-width content):

```tsx
import type { ComponentType } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { BasketIcon, BookIcon, CartIcon, type IconProps } from "./ui/icons";

const tabs: { to: string; label: string; icon: ComponentType<IconProps>; end: boolean }[] = [
  { to: "/", label: "Recipes", icon: BookIcon, end: true },
  { to: "/list", label: "List", icon: BasketIcon, end: false },
  { to: "/kroger", label: "Kroger", icon: CartIcon, end: false },
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <span className="text-lg font-bold tracking-tight text-heading">Bushel</span>
        <nav className="ml-auto hidden gap-1 sm:flex">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-semibold ${
                  isActive ? "bg-primary text-white" : "text-heading hover:bg-canvas"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-6 pb-28 sm:pb-6">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 flex border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] sm:hidden">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold ${
                  isActive ? "text-primary" : "text-muted"
                }`
              }
            >
              <Icon size={22} />
              {t.label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
```

- [ ] **Step 2: Verify the shell tests**

```bash
cd frontend && npm test -- src/components/AppShell.test.tsx src/App.test.tsx && npx tsc -b
```
Expected: PASS — links still resolve by accessible name (the visible text label is the
accessible name; the SVG is `aria-hidden`), `aria-current` still set by `NavLink`, and the
"Bushel" brand text is present.

- [ ] **Step 3: Full suite + build**

```bash
cd frontend && npm test 2>&1 | tail -3 && npm run build
```
Expected: pass; build clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AppShell.tsx
git commit -m "feat(ui): mobile bottom tab bar with SVG icons + safe-area insets"
```

---

## Task 7: Full verification

- [ ] **Step 1: Whole frontend suite + typecheck + build**

```bash
cd frontend && npm test && npx tsc -b && npm run build
```
Expected: all green; no removed-token classes remain (`grep -rnE "tint-amber|tint-green|bg-cream|border-accent|font-heading" src` returns nothing).

- [ ] **Step 2: Backend untouched (sanity)**

No backend files changed; no need to run pytest, but confirm `git status` shows only frontend
changes for this increment.

- [ ] **Step 3: Manual smoke (optional, recommended)**

Run the app and view on a narrow viewport / phone: cool-neutral surfaces, Inter throughout,
the bottom tab bar with SVG icons sitting above the home indicator (safe area), 44px tap
targets, Modal opens with the new close icon. Check each route renders.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** tokens (T1), typography Inter-only (T1), spacing/radius/44px (T1/T4),
  mobile shell + bottom nav + safe areas + viewport (T6/T1), SVG icons (T3/T6), components
  restyled (T4/T5), removed-token migration (T2). Per-row emoji in pages are intentionally
  deferred to those pages' redesign increments (noted in scope).
- **Behavior preserved:** `AppShell` keeps `NavLink` labels/hrefs and `aria-current`; `Modal`
  keeps `role="dialog"` + `aria-label="Close"`; `EmptyState` keeps its `icon` prop; "Bushel"
  text remains. So `AppShell.test`, `App.test`, `Modal.test`, `EmptyState.test` pass unchanged.
- **Token consistency:** `surface/line/heading/ink/muted/primary/primary-hover` keep names
  (new values); `canvas/line-strong/primary-tint/warning(-tint)/danger(-tint)/success(-tint)`
  added; `cream/accent/tint-amber/tint-green` and the `heading` font family removed and all
  usages migrated (verified by grep in T2/T7).
```

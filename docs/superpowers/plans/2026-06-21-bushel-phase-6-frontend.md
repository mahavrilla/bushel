# Phase 6: Frontend Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Bushel web UI into the cohesive, mobile-friendly "Warm Pantry" design with Tailwind, client-side routing, a redesigned app shell, and loading/error/empty states on every screen.

**Architecture:** Add Tailwind CSS (theme = Warm Pantry tokens) and `react-router-dom`. Build a small `components/ui/` primitives layer + an `AppShell` (header nav + mobile bottom tabs). Convert `App.tsx` from `useState` view-switching to routes (3 destinations: Recipes/List/Kroger). Restyle each existing screen to compose the primitives. **Frontend-only — no backend/API changes.**

**Tech Stack:** React 18 + TypeScript + Vite, Tailwind CSS v3, react-router-dom v6, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-06-21-bushel-phase-6-frontend-design.md`

**Conventions (from the existing codebase):**
- All commands run from `frontend/`. Tests: `npm test` (vitest, jsdom, `@testing-library/jest-dom/vitest` auto-loaded via `vite.config.ts`). Type/build check: `npm run build` (`tsc -b && vite build`).
- Components live under `src/`; screens in `src/recipes/`; fetch helpers in `src/api.ts` (unchanged this phase).
- Tailwind classes don't affect tests (jsdom ignores CSS); keep accessible queries working (`getByRole`/`getByLabelText`/`getByText`), so `<label>` must wrap inputs and buttons keep their text/aria-labels.
- **No backend changes.** Do not touch `backend/`.

**Warm Pantry tokens** (used throughout): `cream #FBF7EF`, `surface #FFFDF8`, `primary #C2410C`/`primary-hover #9A3412`, `accent #D97706`, `success #4D7C0F`, `danger #B91C1C`, `ink #44403C`, `heading #7C2D12`, `muted #A8A29E`, `line #ECDFC9`, `tint-amber #FEF3E2`, `tint-green #ECFCCB`. Headings `font-heading` (Fraunces), body `font-sans` (Inter).

---

## Task 1: Install & configure Tailwind

**Files:**
- Modify: `frontend/package.json` (deps)
- Create: `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/src/index.css`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Install Tailwind toolchain**

Run (from `frontend/`):
```bash
npm install -D tailwindcss@^3 postcss autoprefixer
```

- [ ] **Step 2: Create `frontend/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#FBF7EF",
        surface: "#FFFDF8",
        primary: { DEFAULT: "#C2410C", hover: "#9A3412" },
        accent: "#D97706",
        success: "#4D7C0F",
        danger: "#B91C1C",
        ink: "#44403C",
        heading: "#7C2D12",
        muted: "#A8A29E",
        line: "#ECDFC9",
        "tint-amber": "#FEF3E2",
        "tint-green": "#ECFCCB",
      },
      fontFamily: {
        heading: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: { xl: "0.75rem" },
    },
  },
  plugins: [],
};
```

- [ ] **Step 3: Create `frontend/postcss.config.js`**

```js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 4: Create `frontend/src/index.css`**

```css
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-cream text-ink font-sans;
  }
  h1, h2, h3 {
    @apply font-heading text-heading;
  }
}
```

- [ ] **Step 5: Import the stylesheet in `frontend/src/main.tsx`**

Add `import "./index.css";` at the top of `frontend/src/main.tsx` (above the React imports). Leave the rest of the file unchanged for now (BrowserRouter is added in Task 6).

- [ ] **Step 6: Verify the build compiles Tailwind**

Run: `npm run build`
Expected: PASS (tsc + vite build succeed; no Tailwind/PostCSS errors).

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tailwind.config.js frontend/postcss.config.js frontend/src/index.css frontend/src/main.tsx
git commit -m "build(web): add Tailwind CSS + Warm Pantry theme tokens"
```

---

## Task 2: UI primitives — Spinner, Pill, Card

**Files:**
- Create: `frontend/src/components/ui/Spinner.tsx`, `Pill.tsx`, `Card.tsx`
- Test: `frontend/src/components/ui/Spinner.test.tsx`, `Pill.test.tsx`, `Card.test.tsx`

- [ ] **Step 1: Write failing tests**

`frontend/src/components/ui/Spinner.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Spinner } from "./Spinner";

describe("Spinner", () => {
  it("renders an accessible loading indicator", () => {
    render(<Spinner />);
    expect(screen.getByRole("status", { name: /loading/i })).toBeInTheDocument();
  });
});
```

`frontend/src/components/ui/Pill.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Pill } from "./Pill";

describe("Pill", () => {
  it("renders its label and tone class", () => {
    render(<Pill tone="success">In stock</Pill>);
    const el = screen.getByText("In stock");
    expect(el).toBeInTheDocument();
    expect(el.className).toContain("text-success");
  });
});
```

`frontend/src/components/ui/Card.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card } from "./Card";

describe("Card", () => {
  it("renders children inside a surface container", () => {
    render(<Card>hello</Card>);
    const el = screen.getByText("hello");
    expect(el.className).toContain("bg-surface");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- ui/`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the components**

`frontend/src/components/ui/Spinner.tsx`:
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

`frontend/src/components/ui/Pill.tsx`:
```tsx
type Tone = "success" | "danger" | "warning" | "neutral";

const tones: Record<Tone, string> = {
  success: "bg-tint-green text-success",
  danger: "bg-red-100 text-danger",
  warning: "bg-tint-amber text-primary",
  neutral: "bg-stone-100 text-stone-600",
};

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
```

`frontend/src/components/ui/Card.tsx`:
```tsx
export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-line bg-surface p-4 ${className}`}>{children}</div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- ui/`
Expected: PASS (3 files).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Spinner.tsx frontend/src/components/ui/Pill.tsx frontend/src/components/ui/Card.tsx frontend/src/components/ui/Spinner.test.tsx frontend/src/components/ui/Pill.test.tsx frontend/src/components/ui/Card.test.tsx
git commit -m "feat(web): Spinner, Pill, Card primitives"
```

---

## Task 3: UI primitives — Button, Input

**Files:**
- Create: `frontend/src/components/ui/Button.tsx`, `Input.tsx`
- Test: `frontend/src/components/ui/Button.test.tsx`, `Input.test.tsx`

- [ ] **Step 1: Write failing tests**

`frontend/src/components/ui/Button.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

describe("Button", () => {
  it("fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Go" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and shows a spinner while loading", () => {
    render(<Button loading>Send</Button>);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
    expect(screen.getByRole("status", { name: /loading/i })).toBeInTheDocument();
  });
});
```

`frontend/src/components/ui/Input.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Input } from "./Input";

describe("Input", () => {
  it("associates its label and forwards changes", async () => {
    const onChange = vi.fn();
    render(<Input label="Zip code" value="" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText(/zip code/i), "4");
    expect(onChange).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- "ui/Button" "ui/Input"`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the components**

`frontend/src/components/ui/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes } from "react";

import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "link";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-white hover:bg-primary-hover",
  secondary: "border border-line bg-surface text-heading hover:bg-cream",
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
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}
```

`frontend/src/components/ui/Input.tsx`:
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
        className={`rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary ${className}`}
        {...props}
      />
    </label>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- "ui/Button" "ui/Input"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Button.tsx frontend/src/components/ui/Input.tsx frontend/src/components/ui/Button.test.tsx frontend/src/components/ui/Input.test.tsx
git commit -m "feat(web): Button, Input primitives"
```

---

## Task 4: UI primitives — PageHeader, EmptyState, ErrorBanner

**Files:**
- Create: `frontend/src/components/ui/PageHeader.tsx`, `EmptyState.tsx`, `ErrorBanner.tsx`
- Test: `frontend/src/components/ui/PageHeader.test.tsx`, `EmptyState.test.tsx`, `ErrorBanner.test.tsx`

- [ ] **Step 1: Write failing tests**

`frontend/src/components/ui/PageHeader.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("renders a title heading and an action slot", () => {
    render(<PageHeader title="Recipes" action={<button>Add</button>} />);
    expect(screen.getByRole("heading", { name: "Recipes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });
});
```

`frontend/src/components/ui/EmptyState.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows a message and fires the optional action", async () => {
    const onAction = vi.fn();
    render(<EmptyState icon="🧺" message="No recipes yet" actionLabel="Add one" onAction={onAction} />);
    expect(screen.getByText(/no recipes yet/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /add one/i }));
    expect(onAction).toHaveBeenCalledOnce();
  });
});
```

`frontend/src/components/ui/ErrorBanner.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ErrorBanner } from "./ErrorBanner";

describe("ErrorBanner", () => {
  it("renders an alert with optional action", async () => {
    const onAction = vi.fn();
    render(<ErrorBanner message="Session expired" actionLabel="Reconnect" onAction={onAction} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/session expired/i);
    await userEvent.click(screen.getByRole("button", { name: /reconnect/i }));
    expect(onAction).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- "ui/PageHeader" "ui/EmptyState" "ui/ErrorBanner"`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the components**

`frontend/src/components/ui/PageHeader.tsx`:
```tsx
export function PageHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center gap-3">
      <h2 className="text-2xl font-semibold text-heading">{title}</h2>
      {action && <div className="ml-auto">{action}</div>}
    </div>
  );
}
```

`frontend/src/components/ui/EmptyState.tsx`:
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
    <div className="rounded-xl border border-dashed border-line bg-surface p-10 text-center">
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

`frontend/src/components/ui/ErrorBanner.tsx`:
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
      className="mb-4 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger"
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- "ui/PageHeader" "ui/EmptyState" "ui/ErrorBanner"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/PageHeader.tsx frontend/src/components/ui/EmptyState.tsx frontend/src/components/ui/ErrorBanner.tsx frontend/src/components/ui/PageHeader.test.tsx frontend/src/components/ui/EmptyState.test.tsx frontend/src/components/ui/ErrorBanner.test.tsx
git commit -m "feat(web): PageHeader, EmptyState, ErrorBanner primitives"
```

---

## Task 5: react-router + renderWithRouter helper + AppShell

**Files:**
- Modify: `frontend/package.json` (add react-router-dom)
- Create: `frontend/src/test/renderWithRouter.tsx`
- Create: `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/components/AppShell.test.tsx`

- [ ] **Step 1: Install react-router-dom**

Run (from `frontend/`):
```bash
npm install react-router-dom@^6
```

- [ ] **Step 2: Create the test helper `frontend/src/test/renderWithRouter.tsx`**

```tsx
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

/**
 * Render a screen inside a MemoryRouter. Pass `path`/`initialEntries` when the screen
 * reads route params (e.g. path="/recipes/:id", initialEntries=["/recipes/1"]).
 */
export function renderWithRouter(
  ui: ReactElement,
  { path = "/", initialEntries = ["/"] }: { path?: string; initialEntries?: string[] } = {},
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path={path} element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}
```

- [ ] **Step 3: Write the failing AppShell test**

`frontend/src/components/AppShell.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithRouter } from "../test/renderWithRouter";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("renders the three nav destinations as links", () => {
    renderWithRouter(<AppShell />);
    // desktop header + mobile tab bar each render the links, so use getAllByRole.
    expect(screen.getAllByRole("link", { name: /recipes/i }).length).toBeGreaterThan(0);
    const list = screen.getAllByRole("link", { name: /^list$/i })[0];
    const kroger = screen.getAllByRole("link", { name: /kroger/i })[0];
    expect(list).toHaveAttribute("href", "/list");
    expect(kroger).toHaveAttribute("href", "/kroger");
  });
});
```

- [ ] **Step 4: Run it to verify it fails**

Run: `npm test -- AppShell`
Expected: FAIL — module `./AppShell` not found.

- [ ] **Step 5: Implement `frontend/src/components/AppShell.tsx`**

```tsx
import { NavLink, Outlet } from "react-router-dom";

const tabs = [
  { to: "/", label: "Recipes", icon: "📖", end: true },
  { to: "/list", label: "List", icon: "🧺", end: false },
  { to: "/kroger", label: "Kroger", icon: "🛒", end: false },
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-cream text-ink">
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3">
        <span className="font-heading text-lg font-bold text-heading">🧺 Bushel</span>
        <nav className="ml-auto hidden gap-2 sm:flex">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-semibold ${
                  isActive ? "bg-primary text-white" : "text-heading hover:bg-cream"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6 pb-24 sm:pb-6">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 flex border-t border-line bg-surface sm:hidden">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              `flex-1 py-2 text-center text-xs ${isActive ? "font-bold text-primary" : "text-muted"}`
            }
          >
            <div className="text-base">{t.icon}</div>
            {t.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
```

- [ ] **Step 6: Run it to verify it passes**

Run: `npm test -- AppShell`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/test/renderWithRouter.tsx frontend/src/components/AppShell.tsx frontend/src/components/AppShell.test.tsx
git commit -m "feat(web): react-router, renderWithRouter helper, AppShell"
```

---

## Task 6: Routing cutover — App routes + BrowserRouter + screen nav

Switch navigation from `useState`/props to routes. This task changes `App.tsx`, `main.tsx`, and the three screens that took navigation props (`RecipeList`, `AddRecipe`, `RecipeDetail`) to use router hooks, plus their tests. Visual restyle of screens happens in later tasks; here we only change navigation so the app stays green.

**Files:**
- Modify: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`
- Modify: `frontend/src/recipes/RecipeList.tsx`, `RecipeList.test.tsx`
- Modify: `frontend/src/recipes/AddRecipe.tsx`, `AddRecipe.test.tsx`
- Modify: `frontend/src/recipes/RecipeDetail.tsx`, `RecipeDetail.test.tsx`

- [ ] **Step 1: Wrap the app in BrowserRouter (`frontend/src/main.tsx`)**

```tsx
import "./index.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 2: Replace `frontend/src/App.tsx` with routes**

```tsx
import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AddRecipe } from "./recipes/AddRecipe";
import { GroceryList } from "./recipes/GroceryList";
import { KrogerSetup } from "./recipes/KrogerSetup";
import { RecipeDetail } from "./recipes/RecipeDetail";
import { RecipeList } from "./recipes/RecipeList";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<RecipeList />} />
        <Route path="recipes/new" element={<AddRecipe />} />
        <Route path="recipes/:id" element={<RecipeDetail />} />
        <Route path="list" element={<GroceryList />} />
        <Route path="kroger" element={<KrogerSetup />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 3: Convert `RecipeList` to router nav**

Replace `frontend/src/recipes/RecipeList.tsx` (drops the `onOpen` prop; rows link to `/recipes/:id`; keeps current plain markup — restyled in Task 7):
```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { addRecipeToList, listRecipes } from "../api";
import type { RecipeSummary } from "./types";

export function RecipeList() {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);

  useEffect(() => {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, []);

  if (recipes === null) return <p>Loading…</p>;
  if (recipes.length === 0) return <p>No recipes yet. Add one to get started.</p>;

  return (
    <ul>
      {recipes.map((r) => (
        <li key={r.id}>
          <Link to={`/recipes/${r.id}`}>
            {r.title} ({r.servings} servings)
          </Link>
          <button aria-label={`Add ${r.title} to list`} onClick={() => addRecipeToList(r.id)}>
            Add to list
          </button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: Update `RecipeList.test.tsx`**

Replace the file (wrap in router; the open action is now a link with an href):
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithRouter } from "../test/renderWithRouter";
import { RecipeList } from "./RecipeList";

afterEach(() => vi.restoreAllMocks());

describe("RecipeList", () => {
  it("links each recipe to its detail route", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    );
    renderWithRouter(<RecipeList />);
    const link = await screen.findByRole("link", { name: /pancakes/i });
    expect(link).toHaveAttribute("href", "/recipes/1");
  });

  it("shows an empty state when there are no recipes", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
    renderWithRouter(<RecipeList />);
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });

  it("adds a recipe to the list", async () => {
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 1, status: "draft", recipes: [], items: [] }), { status: 200 }),
      );
    renderWithRouter(<RecipeList />);
    await userEvent.click(await screen.findByRole("button", { name: /add pancakes to list/i }));
    await waitFor(() =>
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining("/list/recipes"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
});
```

- [ ] **Step 5: Convert `AddRecipe` to router nav** (three targeted edits in `frontend/src/recipes/AddRecipe.tsx`; the rest of the file is restyled in Task 8)

Edit 1 — add the import below the existing `import { useState } from "react";`:
```tsx
import { useNavigate } from "react-router-dom";
```
Edit 2 — replace the function signature line:
```tsx
export function AddRecipe({ onCreated }: { onCreated: (id: number) => void }) {
```
with:
```tsx
export function AddRecipe() {
  const navigate = useNavigate();
```
Edit 3 — in `run()`, replace:
```tsx
      onCreated(recipe.id);
```
with:
```tsx
      navigate(`/recipes/${recipe.id}`);
```

- [ ] **Step 6: Update `AddRecipe.test.tsx`**

Replace the file (router with a destination route so navigation is observable):
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AddRecipe } from "./AddRecipe";

afterEach(() => vi.restoreAllMocks());

function renderAddRecipe() {
  return render(
    <MemoryRouter initialEntries={["/recipes/new"]}>
      <Routes>
        <Route path="/recipes/new" element={<AddRecipe />} />
        <Route path="/recipes/:id" element={<div>detail screen</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AddRecipe", () => {
  it("navigates to the new recipe after manual create", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 7, title: "X", servings: 1, source_url: null, ingredients: [] }), { status: 200 }),
    );
    renderAddRecipe();
    await userEvent.type(screen.getByLabelText(/title/i), "Bread");
    await userEvent.type(screen.getByLabelText(/ingredients/i), "2 cups flour");
    await userEvent.click(screen.getByRole("button", { name: /save recipe/i }));
    expect(await screen.findByText(/detail screen/i)).toBeInTheDocument();
  });

  it("shows an error when import fails", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 500 }));
    renderAddRecipe();
    await userEvent.type(screen.getByLabelText(/recipe url/i), "http://x");
    await userEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Convert `RecipeDetail` to route param** (two targeted edits in `frontend/src/recipes/RecipeDetail.tsx`; the inner `Row` and JSX are restyled in Task 9)

Edit 1 — add the import below the existing `import { useEffect, useState } from "react";`:
```tsx
import { useParams } from "react-router-dom";
```
Edit 2 — replace the function signature line:
```tsx
export function RecipeDetail({ recipeId }: { recipeId: number }) {
```
with:
```tsx
export function RecipeDetail() {
  const { id } = useParams();
  const recipeId = Number(id);
```

- [ ] **Step 8: Update `RecipeDetail.test.tsx`**

Replace the render calls to use the router helper with a param. Full file:
```tsx
import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithRouter } from "../test/renderWithRouter";
import { RecipeDetail } from "./RecipeDetail";

afterEach(() => vi.restoreAllMocks());

const recipe = {
  id: 1,
  title: "Pancakes",
  servings: 4,
  source_url: null,
  ingredients: [
    { id: 10, raw_text: "2 cups flour", qty: 2, unit: "cup", ingredient_id: 5, ingredient_name: "flour", parse_source: "library", needs_review: false },
  ],
};

function show() {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify(recipe), { status: 200 }));
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
}

describe("RecipeDetail", () => {
  it("renders the recipe title", async () => {
    show();
    expect(await screen.findByRole("heading", { name: /pancakes/i })).toBeInTheDocument();
  });

  it("shows the reviewed status", async () => {
    show();
    expect(await screen.findByText(/all items reviewed/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 9: Replace `App.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import * as api from "./api";
import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
  });
  afterEach(() => vi.restoreAllMocks());

  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>,
    );
  }

  it("renders the Bushel brand and recipes at /", async () => {
    renderAt("/");
    expect(await screen.findByText(/bushel/i)).toBeInTheDocument();
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });

  it("renders the grocery list route", async () => {
    vi.spyOn(api, "getList").mockResolvedValue({ id: 1, status: "draft", recipes: [], items: [] });
    // GroceryList embeds MatchAndSend (Task 12), which calls getMatch on mount — mock it so
    // this test keeps passing after that task lands.
    vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
    renderAt("/list");
    expect(await screen.findByRole("heading", { name: /grocery list/i })).toBeInTheDocument();
  });

  it("renders the Kroger route", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: false, expired: false });
    vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
    renderAt("/kroger");
    expect(await screen.findByRole("heading", { name: /^kroger$/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 10: Run the full suite + build**

Run: `npm test` then `npm run build`
Expected: all tests PASS; build succeeds. (Screens are routed and functional; visual restyle comes next.)

- [ ] **Step 11: Commit**

```bash
git add frontend/src/main.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/recipes/RecipeList.tsx frontend/src/recipes/RecipeList.test.tsx frontend/src/recipes/AddRecipe.tsx frontend/src/recipes/AddRecipe.test.tsx frontend/src/recipes/RecipeDetail.tsx frontend/src/recipes/RecipeDetail.test.tsx
git commit -m "feat(web): cut navigation over to react-router (3 destinations)"
```

---

## Task 7: Restyle RecipeList

**Files:**
- Modify: `frontend/src/recipes/RecipeList.tsx`
- Modify: `frontend/src/recipes/RecipeList.test.tsx` (add empty-action assertion)

- [ ] **Step 1: Update the test for the new structure**

Add this test to `RecipeList.test.tsx` (inside the `describe`):
```tsx
it("offers an Add recipe action in the header", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
  renderWithRouter(<RecipeList />);
  const add = await screen.findByRole("link", { name: /add recipe/i });
  expect(add).toHaveAttribute("href", "/recipes/new");
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test -- recipes/RecipeList`
Expected: FAIL — no "Add recipe" link yet.

- [ ] **Step 3: Restyle `frontend/src/recipes/RecipeList.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { addRecipeToList, listRecipes } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import type { RecipeSummary } from "./types";

export function RecipeList() {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);

  useEffect(() => {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, []);

  const addAction = (
    <Link
      to="/recipes/new"
      className="inline-flex items-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
    >
      + Add recipe
    </Link>
  );

  return (
    <div>
      <PageHeader title="Recipes" action={addAction} />
      {recipes === null ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : recipes.length === 0 ? (
        <EmptyState icon="📖" message="No recipes yet. Add one to get started." />
      ) : (
        <ul className="flex flex-col gap-2">
          {recipes.map((r) => (
            <li key={r.id}>
              <Card className="flex items-center gap-3">
                <Link to={`/recipes/${r.id}`} className="font-medium text-heading hover:underline">
                  {r.title}
                </Link>
                <span className="text-sm text-muted">{r.servings} servings</span>
                <Button
                  variant="secondary"
                  className="ml-auto"
                  aria-label={`Add ${r.title} to list`}
                  onClick={() => addRecipeToList(r.id)}
                >
                  Add to list
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- recipes/RecipeList`
Expected: PASS (link to `/recipes/1`, empty state, add-to-list POST, add-recipe header link).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeList.tsx frontend/src/recipes/RecipeList.test.tsx
git commit -m "feat(web): restyle RecipeList (Warm Pantry)"
```

---

## Task 8: Restyle AddRecipe

**Files:**
- Modify: `frontend/src/recipes/AddRecipe.tsx`

- [ ] **Step 1: Restyle `frontend/src/recipes/AddRecipe.tsx`** (behavior unchanged; the `AddRecipe.test.tsx` from Task 6 must keep passing — it queries `/title/i`, `/ingredients/i`, `/recipe url/i` labels and the `Import`/`Save recipe` buttons, so preserve those label texts and button names)

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createRecipe, importRecipe } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";

export function AddRecipe() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [servings, setServings] = useState(1);
  const [lines, setLines] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<{ id: number }>) {
    setBusy(true);
    setError(null);
    try {
      const recipe = await action();
      navigate(`/recipes/${recipe.id}`);
    } catch {
      setError("Couldn't import — check the URL or try manual entry.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Add recipe" />
      {error && <ErrorBanner message={error} />}

      <Card className="flex flex-col gap-3">
        <h3 className="text-lg font-semibold text-heading">Import by URL</h3>
        <Input label="Recipe URL" value={url} onChange={(e) => setUrl(e.target.value)} />
        <Button disabled={!url} loading={busy} className="self-start" onClick={() => run(() => importRecipe(url))}>
          Import
        </Button>
      </Card>

      <Card className="flex flex-col gap-3">
        <h3 className="text-lg font-semibold text-heading">Or enter manually</h3>
        <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Input
          label="Servings"
          type="number"
          value={servings}
          onChange={(e) => setServings(Number(e.target.value))}
        />
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Ingredients (one per line)</span>
          <textarea
            className="min-h-24 rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            value={lines}
            onChange={(e) => setLines(e.target.value)}
          />
        </label>
        <Button
          disabled={!title.trim() || !lines.trim()}
          loading={busy}
          className="self-start"
          onClick={() => run(() => createRecipe(title, servings, lines.split("\n")))}
        >
          Save recipe
        </Button>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `npm test -- recipes/AddRecipe`
Expected: PASS (navigation on save, error alert on failed import).

Note: `Button` uses `loading` for the busy spinner and `disabled` for empty fields — when `busy` is true the button is disabled via `loading`, preserving the old disabled-while-busy behavior.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/recipes/AddRecipe.tsx
git commit -m "feat(web): restyle AddRecipe (Warm Pantry)"
```

---

## Task 9: Restyle RecipeDetail

**Files:**
- Modify: `frontend/src/recipes/RecipeDetail.tsx`

- [ ] **Step 1: Restyle `frontend/src/recipes/RecipeDetail.tsx`** (preserve the label texts `Qty for …` / `Unit for …`, the `Save …` button names, the `role="status"` review summary, and the heading — the Task 6 tests query these)

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getRecipe, updateIngredient } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import type { IngredientRead, RecipeRead } from "./types";

function Row({
  recipeId,
  ingredient,
  onSaved,
}: {
  recipeId: number;
  ingredient: IngredientRead;
  onSaved: (recipe: RecipeRead) => void;
}) {
  const [qty, setQty] = useState(ingredient.qty?.toString() ?? "");
  const [unit, setUnit] = useState(ingredient.unit ?? "");

  async function save() {
    const updated = await updateIngredient(recipeId, ingredient.id, {
      qty: qty === "" ? undefined : Number(qty),
      unit: unit === "" ? undefined : unit,
    });
    onSaved(updated);
  }

  return (
    <Card className={ingredient.needs_review ? "border-accent bg-tint-amber" : ""}>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm text-muted">{ingredient.raw_text}</span>
        <span className="text-muted">→</span>
        <strong className="text-heading">{ingredient.ingredient_name}</strong>
        {ingredient.needs_review && <Pill tone="warning">Needs review</Pill>}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Input label={`Qty for ${ingredient.raw_text}`} value={qty} onChange={(e) => setQty(e.target.value)} className="w-24" />
        <Input label={`Unit for ${ingredient.raw_text}`} value={unit} onChange={(e) => setUnit(e.target.value)} className="w-28" />
        <Button variant="secondary" onClick={save}>
          Save {ingredient.raw_text}
        </Button>
      </div>
    </Card>
  );
}

export function RecipeDetail() {
  const { id } = useParams();
  const recipeId = Number(id);
  const [recipe, setRecipe] = useState<RecipeRead | null>(null);

  useEffect(() => {
    getRecipe(recipeId).then(setRecipe).catch(() => setRecipe(null));
  }, [recipeId]);

  if (recipe === null)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );

  const flagged = recipe.ingredients.filter((i) => i.needs_review).length;

  return (
    <div>
      <PageHeader title={recipe.title} />
      <p role="status" className="mb-4 text-sm text-muted">
        {flagged > 0
          ? `${flagged} item${flagged === 1 ? "" : "s"} need${flagged === 1 ? "s" : ""} review`
          : "All items reviewed ✓"}
      </p>
      <ul className="flex flex-col gap-3">
        {recipe.ingredients.map((ing) => (
          <li key={ing.id}>
            <Row recipeId={recipe.id} ingredient={ing} onSaved={setRecipe} />
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `npm test -- recipes/RecipeDetail`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/recipes/RecipeDetail.tsx
git commit -m "feat(web): restyle RecipeDetail (Warm Pantry)"
```

---

## Task 10: Restyle KrogerSetup

**Files:**
- Modify: `frontend/src/recipes/KrogerSetup.tsx`

- [ ] **Step 1: Restyle `frontend/src/recipes/KrogerSetup.tsx`** (preserve behavior + the existing `KrogerSetup.test.tsx` queries: "Connect Kroger" button, `/zip/i` label, "Find stores" button, "Use this store" button, "Selected store: …" text)

```tsx
import { useEffect, useState } from "react";

import { getKrogerLoginUrl, getKrogerStatus, getMatch, searchLocations, setStore } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import type { KrogerLocation, KrogerStatus } from "./types";

export function KrogerSetup() {
  const [status, setStatus] = useState<KrogerStatus | null>(null);
  const [zip, setZip] = useState("");
  const [stores, setStores] = useState<KrogerLocation[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getKrogerStatus().then(setStatus).catch(() => setStatus(null));
    getMatch().then((m) => setSelected(m.store_location_id)).catch(() => {});
  }, []);

  async function connect() {
    const { url } = await getKrogerLoginUrl();
    window.location.href = url;
  }

  async function findStores() {
    setBusy(true);
    try {
      setStores(await searchLocations(zip));
    } finally {
      setBusy(false);
    }
  }

  async function choose(locationId: string) {
    const match = await setStore(locationId);
    setSelected(match.store_location_id);
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Kroger" />

      <Card>
        {status?.connected ? (
          <p className="text-ink">
            Connected{status.expired ? " — session expired, reconnect below." : "."}
          </p>
        ) : (
          <Button onClick={connect}>Connect Kroger</Button>
        )}
      </Card>

      <Card className="flex flex-col gap-3">
        <h3 className="text-lg font-semibold text-heading">Home store</h3>
        {selected && <p className="text-sm text-success">Selected store: {selected}</p>}
        <div className="flex items-end gap-2">
          <Input label="Zip code" value={zip} onChange={(e) => setZip(e.target.value)} className="w-32" />
          <Button variant="secondary" loading={busy} onClick={findStores}>
            Find stores
          </Button>
        </div>
        <ul className="flex flex-col gap-2">
          {stores.map((s) => (
            <li key={s.location_id} className="flex items-center gap-3 rounded-xl border border-line bg-surface px-3 py-2">
              <div>
                <div className="text-sm font-medium text-heading">{s.name}</div>
                <div className="text-xs text-muted">{s.address}</div>
              </div>
              <Button variant="secondary" className="ml-auto" onClick={() => choose(s.location_id)}>
                Use this store
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `npm test -- recipes/KrogerSetup`
Expected: PASS (connect button, store search, select + "Selected store: L1", hydrate on mount).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/recipes/KrogerSetup.tsx
git commit -m "feat(web): restyle KrogerSetup (Warm Pantry)"
```

---

## Task 11: Rename MatchReview → MatchAndSend and restyle

**Files:**
- Rename: `frontend/src/recipes/MatchReview.tsx` → `frontend/src/recipes/MatchAndSend.tsx`
- Rename: `frontend/src/recipes/MatchReview.test.tsx` → `frontend/src/recipes/MatchAndSend.test.tsx`

- [ ] **Step 1: Move the test file and update it**

```bash
git mv frontend/src/recipes/MatchReview.test.tsx frontend/src/recipes/MatchAndSend.test.tsx
git mv frontend/src/recipes/MatchReview.tsx frontend/src/recipes/MatchAndSend.tsx
```

Replace `frontend/src/recipes/MatchAndSend.test.tsx` (same behavior, new component name + heading "Review & send"):
```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ApiError } from "../api";
import { MatchAndSend } from "./MatchAndSend";

const baseMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    {
      item_id: 1,
      ingredient_id: 2,
      ingredient_name: "flour",
      total_qty: 3,
      total_unit: "lb",
      purchase_qty: 1,
      purchase_qty_estimated: true,
      kroger_upc: null,
      current: null,
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

describe("MatchAndSend", () => {
  it("lists items and flags estimated quantities", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    render(<MatchAndSend />);
    expect(await screen.findByText(/flour/)).toBeInTheDocument();
    expect(screen.getByText(/check quantity/i)).toBeInTheDocument();
  });

  it("searches products for an item", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const search = vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" },
    ]);
    render(<MatchAndSend />);
    fireEvent.click(await screen.findByRole("button", { name: /find product/i }));
    await waitFor(() => expect(search).toHaveBeenCalledWith(1, "flour"));
    expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
  });

  it("sends the cart and shows the result", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const send = vi.spyOn(api, "sendCart").mockResolvedValue({
      status: "sent_to_kroger",
      results: [{ upc: "0001", ok: true, error: null }],
    });
    render(<MatchAndSend />);
    fireEvent.click(await screen.findByRole("button", { name: /send to kroger cart/i }));
    await waitFor(() => expect(send).toHaveBeenCalledWith("PICKUP"));
    expect(await screen.findByText(/sent_to_kroger/)).toBeInTheDocument();
  });

  it("prompts to reconnect when send returns reauth_required (409)", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    vi.spyOn(api, "sendCart").mockRejectedValue(new ApiError(409));
    render(<MatchAndSend />);
    fireEvent.click(await screen.findByRole("button", { name: /send to kroger cart/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reconnect/i);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test -- recipes/MatchAndSend`
Expected: FAIL — `MatchAndSend` export not found (file still exports `MatchReview`).

- [ ] **Step 3: Restyle `frontend/src/recipes/MatchAndSend.tsx`** (export renamed to `MatchAndSend`; keep all behavior; "Send to Kroger cart" / "Find product" names and the `role="alert"` reauth path preserved)

```tsx
import { useEffect, useState } from "react";

import { ApiError, confirmProduct, getMatch, searchItemProducts, sendCart } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import type { MatchData, ProductChoice, SendResult } from "./types";

export function MatchAndSend() {
  const [match, setMatch] = useState<MatchData | null>(null);
  const [choices, setChoices] = useState<Record<number, ProductChoice[]>>({});
  const [modality, setModality] = useState("PICKUP");
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMatch().then(setMatch).catch(() => setMatch(null));
  }, []);

  function report(err: unknown) {
    if (err instanceof ApiError && err.status === 409) {
      setError("Your Kroger session expired — reconnect on the Kroger tab, then try again.");
    } else {
      setError("Something went wrong talking to Kroger. Please try again.");
    }
  }

  async function find(itemId: number, name: string | null) {
    setError(null);
    try {
      const results = await searchItemProducts(itemId, name ?? "");
      setChoices((c) => ({ ...c, [itemId]: results }));
    } catch (err) {
      report(err);
    }
  }

  async function pick(itemId: number, p: ProductChoice) {
    setError(null);
    try {
      setMatch(
        await confirmProduct(itemId, {
          kroger_upc: p.upc,
          kroger_description: p.description,
          package_size: p.size,
        }),
      );
    } catch (err) {
      report(err);
    }
  }

  async function send() {
    setError(null);
    try {
      setSendResult(await sendCart(modality));
      setMatch(await getMatch());
    } catch (err) {
      report(err);
    }
  }

  if (!match)
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Review &amp; send</h3>
      {error && <ErrorBanner message={error} />}
      {!match.connected && <p className="text-sm text-muted">Connect your Kroger account first.</p>}
      {!match.store_location_id && <p className="text-sm text-muted">Pick a home store first.</p>}

      <ul className="flex flex-col gap-3">
        {match.items.map((it) => (
          <li key={it.item_id} className="rounded-xl border border-line p-3">
            <div className="flex flex-wrap items-center gap-2">
              <strong className="text-heading">{it.ingredient_name}</strong>
              <span className="text-sm text-muted">
                need {it.total_qty ?? "?"} {it.total_unit ?? ""}; buy {it.purchase_qty}
              </span>
              {it.purchase_qty_estimated && <Pill tone="warning">Check quantity</Pill>}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-ink">
                {it.current ? `Product: ${it.current.description}` : "No product chosen"}
              </span>
              <Button variant="secondary" className="ml-auto" onClick={() => find(it.item_id, it.ingredient_name)}>
                Find product
              </Button>
            </div>
            <ul className="mt-2 flex flex-col gap-1">
              {(choices[it.item_id] ?? []).map((p) => (
                <li key={p.upc} className="flex items-center gap-2 text-sm">
                  <span>{p.description}</span>
                  {p.size && <span className="text-muted">({p.size})</span>}
                  {p.price != null && <span className="text-muted">${p.price.toFixed(2)}</span>}
                  {p.stock_level === "TEMPORARILY_OUT_OF_STOCK" && <Pill tone="danger">Out of stock</Pill>}
                  <Button variant="link" className="ml-auto" onClick={() => pick(it.item_id, p)}>
                    Choose
                  </Button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Modality</span>
          <select
            className="rounded-xl border border-line bg-surface px-3 py-2 text-ink"
            value={modality}
            onChange={(e) => setModality(e.target.value)}
          >
            <option value="PICKUP">Pickup</option>
            <option value="DELIVERY">Delivery</option>
          </select>
        </label>
        <Button className="ml-auto" onClick={send}>
          Send to Kroger cart
        </Button>
      </div>

      {sendResult && (
        <div className="rounded-xl bg-cream p-3">
          <p className="text-sm font-medium text-heading">Status: {sendResult.status}</p>
          <ul className="mt-1 flex flex-col gap-1">
            {sendResult.results.map((r) => (
              <li key={r.upc} className="text-sm">
                {r.upc}: {r.ok ? "added" : `failed — ${r.error}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- recipes/MatchAndSend`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/MatchAndSend.tsx frontend/src/recipes/MatchAndSend.test.tsx
git commit -m "feat(web): rename MatchReview -> MatchAndSend, restyle"
```

---

## Task 12: Restyle GroceryList + compose MatchAndSend

**Files:**
- Modify: `frontend/src/recipes/GroceryList.tsx`
- Modify: `frontend/src/recipes/GroceryList.test.tsx`

- [ ] **Step 1: Update the test**

Replace `frontend/src/recipes/GroceryList.test.tsx`. It mocks `getList` (and `getMatch`, since the embedded `MatchAndSend` calls it on mount):
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { GroceryList } from "./GroceryList";

beforeEach(() => {
  vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
});
afterEach(() => vi.restoreAllMocks());

const list = {
  id: 1,
  status: "draft",
  recipes: [{ recipe_id: 9, title: "Pancakes", servings: 4, default_servings: 2 }],
  items: [
    { ingredient_id: 5, ingredient_name: "flour", category: "baking", quantities: [{ qty: 3, unit: "cup" }], source_recipe_ids: [9], pantry_status: "needed" },
  ],
};

describe("GroceryList", () => {
  it("renders recipes and shopping items", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    expect(await screen.findByText(/pancakes/i)).toBeInTheDocument();
    expect(await screen.findByText(/flour/i)).toBeInTheDocument();
  });

  it("shows an empty state when no recipes are on the list", async () => {
    vi.spyOn(api, "getList").mockResolvedValue({ id: 1, status: "draft", recipes: [], items: [] });
    render(<GroceryList />);
    expect(await screen.findByText(/no recipes on your list/i)).toBeInTheDocument();
  });

  it("includes the Review & send panel", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    expect(await screen.findByText(/review & send/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test -- recipes/GroceryList`
Expected: FAIL — no "Review & send" panel yet (and possibly the empty-state text differs).

- [ ] **Step 3: Restyle `frontend/src/recipes/GroceryList.tsx`** (compose `MatchAndSend`; keep `aria-label`s `Servings for …` / `Update …` / `Remove …`)

```tsx
import { useEffect, useState } from "react";

import { getList, removeRecipeFromList, updateListServings } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import type { GroceryListData, ListRecipe, SubQuantity } from "./types";
import { MatchAndSend } from "./MatchAndSend";

function formatQuantities(quantities: SubQuantity[]): string {
  if (quantities.length === 0) return "";
  return quantities
    .map((q) =>
      q.qty === null ? `as needed${q.unit ? ` (${q.unit})` : ""}` : `${q.qty}${q.unit ? ` ${q.unit}` : ""}`,
    )
    .join(" + ");
}

function RecipeRow({
  recipe,
  onChange,
}: {
  recipe: ListRecipe;
  onChange: (list: GroceryListData) => void;
}) {
  const [servings, setServings] = useState(recipe.servings.toString());

  useEffect(() => {
    setServings(recipe.servings.toString());
  }, [recipe.servings]);

  async function handleUpdate() {
    const n = Number(servings);
    if (servings.trim() === "" || !Number.isFinite(n)) return;
    onChange(await updateListServings(recipe.recipe_id, n));
  }

  return (
    <li className="flex flex-wrap items-end gap-2 rounded-xl border border-line bg-surface px-3 py-2">
      <span className="font-medium text-heading">{recipe.title}</span>
      <Input
        label={`Servings for ${recipe.title}`}
        value={servings}
        onChange={(e) => setServings(e.target.value)}
        className="w-20"
      />
      <Button variant="secondary" aria-label={`Update ${recipe.title}`} onClick={handleUpdate}>
        Update
      </Button>
      <Button
        variant="link"
        aria-label={`Remove ${recipe.title}`}
        onClick={async () => onChange(await removeRecipeFromList(recipe.recipe_id))}
      >
        Remove
      </Button>
    </li>
  );
}

export function GroceryList() {
  const [list, setList] = useState<GroceryListData | null>(null);

  useEffect(() => {
    getList().then(setList).catch(() => setList(null));
  }, []);

  if (list === null)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Grocery list" />

      {list.recipes.length === 0 ? (
        <EmptyState icon="🧺" message="No recipes on your list yet. Add some from the Recipes tab." />
      ) : (
        <>
          <Card className="flex flex-col gap-2">
            <h3 className="text-lg font-semibold text-heading">Recipes</h3>
            <ul className="flex flex-col gap-2">
              {list.recipes.map((r) => (
                <RecipeRow key={r.recipe_id} recipe={r} onChange={setList} />
              ))}
            </ul>
          </Card>

          <Card className="flex flex-col gap-2">
            <h3 className="text-lg font-semibold text-heading">Shopping list</h3>
            <ul className="flex flex-col gap-1">
              {list.items.map((item) => (
                <li key={item.ingredient_id} className="flex items-center gap-2 border-b border-line py-1.5 text-sm last:border-0">
                  <strong className="text-heading">{item.ingredient_name}</strong>
                  <span className="text-ink">{formatQuantities(item.quantities)}</span>
                  {item.category && <span className="ml-auto text-xs text-muted">{item.category}</span>}
                </li>
              ))}
            </ul>
          </Card>

          <MatchAndSend />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- recipes/GroceryList`
Expected: PASS (recipes + items, empty state, "Review & send" panel present).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/GroceryList.tsx frontend/src/recipes/GroceryList.test.tsx
git commit -m "feat(web): restyle GroceryList + embed Match & send panel"
```

---

## Task 13: Final verification & cleanup

**Files:**
- (no new code; verification + any leftover cleanup)

- [ ] **Step 1: Confirm no leftover references to old APIs**

Run (from `frontend/`):
```bash
grep -rn "MatchReview\|onOpen\|onCreated\|recipeId=" src/ || echo "clean"
```
Expected: `clean` (the old prop-based nav and the old component name are gone). If any references remain in non-test code, fix them to use the router-based equivalents.

- [ ] **Step 2: Run the full test suite**

Run: `npm test`
Expected: ALL tests pass (UI primitives, AppShell, App routes, all six screens).

- [ ] **Step 3: Run the production build**

Run: `npm run build`
Expected: PASS (tsc has no type errors; vite build succeeds; Tailwind classes present).

- [ ] **Step 4: Manual visual check (optional but recommended)**

Run: `npm run dev`, open http://localhost:5173. Confirm: Warm Pantry styling, the header nav + (resize to mobile width) bottom tab bar, navigating between Recipes/List/Kroger updates the URL, and loading/empty states render. (The Docker `web` container must be rebuilt — `docker compose up --build web` — to see this through the container, but `npm run dev` is faster for a visual check.)

- [ ] **Step 5: Commit any cleanup**

```bash
git add -A frontend/
git commit -m "chore(web): Phase 6 final cleanup + verification" --allow-empty
```

---

## Done criteria

- `npm test` and `npm run build` both green.
- Every screen restyled in Warm Pantry, with loading/error/empty states.
- 3-destination router nav (Recipes/List/Kroger) with desktop header + mobile bottom tabs; Add recipe is a header action, Match & send is a panel on `/list`.
- No backend changes; all existing API behavior preserved.
- Phase 6 merged to `master` via finishing-a-development-branch.

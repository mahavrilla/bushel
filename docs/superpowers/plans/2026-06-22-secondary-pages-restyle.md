# Secondary Pages Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle and polish the three simpler screens — Recipes list, Add recipe, Kroger setup — to match the shipped visual foundation, with three real interaction fixes: inline "Added ✓" confirmation, a URL/Manual segmented toggle, and explicit Kroger connection states.

**Architecture:** Three independent React page reworks, each touching only its own component file plus its test file. No backend, no new routes, no new shared components. Reuses existing foundation primitives (`SegmentedControl`, `Pill`, `TrashIcon`, `Button`, `Card`, `Input`). Frontend-only, TDD.

**Tech Stack:** React + TypeScript + Vite + Tailwind; Vitest + Testing Library (`@testing-library/react`, `@testing-library/user-event`).

**Spec:** `docs/superpowers/specs/2026-06-22-secondary-pages-restyle-design.md`

**Run tests from `frontend/`:** `cd frontend && npm test -- <file>` (vitest, non-watch in CI mode runs once). Type-check: `npx tsc -b`. Build: `npm run build`.

---

## File Structure

- `frontend/src/recipes/RecipeList.tsx` (modify) — sticky search; new colocated `AddToListButton` component (inline "Added ✓"); `TrashIcon` delete.
- `frontend/src/recipes/RecipeList.test.tsx` (modify) — add inline-confirmation + add-error tests.
- `frontend/src/recipes/AddRecipe.tsx` (modify) — `SegmentedControl` [URL · Manual]; render only the active mode's fields.
- `frontend/src/recipes/AddRecipe.test.tsx` (modify) — switch existing manual/extract tests to Manual mode; add a mode-toggle test.
- `frontend/src/recipes/KrogerSetup.tsx` (modify) — connection state via `Pill` + Reconnect; clearer home-store line.
- `frontend/src/recipes/KrogerSetup.test.tsx` (modify) — add connected-pill + expired/reconnect tests.

No other files change. All existing primitives are already implemented:
- `SegmentedControl<T extends string>({ options: {value,label}[], value, onChange })` — `frontend/src/components/ui/SegmentedControl.tsx`; renders `role="tablist"` with `role="tab"` buttons.
- `Pill({ tone?: "success"|"danger"|"warning"|"neutral", children })` — `frontend/src/components/ui/Pill.tsx`.
- `TrashIcon` (decorative `aria-hidden` SVG, `size` prop) — `frontend/src/components/ui/icons.tsx`.

---

### Task 1: Recipes list — sticky search, inline "Added ✓", TrashIcon

**Files:**
- Modify: `frontend/src/recipes/RecipeList.tsx`
- Test: `frontend/src/recipes/RecipeList.test.tsx`

Current `RecipeList.tsx` renders, per card, a fire-and-forget `<Button onClick={() => addRecipeToList(r.id)}>Add to list</Button>` and a `<Button variant="link">🗑</Button>`. The search `<Input type="search">` sits in a `<div className="mb-4">`. We add inline confirmation feedback, make the search sticky, and swap the emoji for `TrashIcon`. Errors surface through the existing page-level `ErrorBanner` (the `error`/`setError` state already present).

- [ ] **Step 1: Write the failing tests**

Add these two tests to `frontend/src/recipes/RecipeList.test.tsx` (inside the existing `describe("RecipeList", ...)` block). Keep all existing tests as-is.

```tsx
it("confirms inline after adding to the list, then resets", async () => {
  vi.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  vi.spyOn(global, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 1, status: "draft", recipes: [], items: [] }), { status: 200 }),
    );
  renderWithRouter(<RecipeList />);
  const btn = await screen.findByRole("button", { name: /add pancakes to list/i });
  await user.click(btn);
  expect(await screen.findByText("Added ✓")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /add pancakes to list/i })).toBeDisabled();
  await vi.advanceTimersByTimeAsync(1600);
  expect(screen.getByText("Add to list")).toBeInTheDocument();
  vi.useRealTimers();
});

it("surfaces an error when adding to the list fails", async () => {
  vi.spyOn(global, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    )
    .mockResolvedValueOnce(new Response("nope", { status: 500 }));
  renderWithRouter(<RecipeList />);
  await userEvent.click(await screen.findByRole("button", { name: /add pancakes to list/i }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- RecipeList`
Expected: FAIL — the new "Added ✓" text never appears (button is fire-and-forget), and no `alert` renders on add failure. Existing tests still pass.

- [ ] **Step 3: Implement the changes**

Replace the entire contents of `frontend/src/recipes/RecipeList.tsx` with:

```tsx
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { addRecipeToList, deleteRecipe, listRecipes } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { TrashIcon } from "../components/ui/icons";
import type { RecipeSummary } from "./types";

function AddToListButton({
  recipeId,
  title,
  onError,
}: {
  recipeId: number;
  title: string;
  onError: (message: string) => void;
}) {
  const [state, setState] = useState<"idle" | "adding" | "added">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  async function add() {
    setState("adding");
    try {
      await addRecipeToList(recipeId);
      setState("added");
      timer.current = setTimeout(() => setState("idle"), 1500);
    } catch {
      onError(`Could not add ${title} to your list. Please try again.`);
      setState("idle");
    }
  }

  return (
    <Button
      variant="secondary"
      className="ml-auto"
      aria-label={`Add ${title} to list`}
      disabled={state !== "idle"}
      onClick={add}
    >
      {state === "added" ? "Added ✓" : "Add to list"}
    </Button>
  );
}

export function RecipeList() {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  function load() {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }

  useEffect(() => {
    load();
  }, []);

  async function remove(r: RecipeSummary) {
    if (!window.confirm(`Delete ${r.title}? This also removes it from your grocery list.`)) return;
    setError(null);
    try {
      await deleteRecipe(r.id);
      load();
    } catch {
      setError("Could not delete that recipe. Please try again.");
    }
  }

  const addAction = (
    <Link
      to="/recipes/new"
      className="inline-flex min-h-[44px] items-center rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover active:bg-primary-hover"
    >
      + Add recipe
    </Link>
  );

  const filtered =
    recipes?.filter((r) => r.title.toLowerCase().includes(query.trim().toLowerCase())) ?? [];

  return (
    <div>
      <PageHeader title="Recipes" action={addAction} />
      {error && <ErrorBanner message={error} />}
      {recipes === null ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : recipes.length === 0 ? (
        <EmptyState icon="📖" message="No recipes yet. Add one to get started." />
      ) : (
        <>
          <div className="sticky top-0 z-10 bg-canvas pb-3 pt-1">
            <Input
              type="search"
              label="Search recipes"
              placeholder="Search recipes…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {filtered.length === 0 ? (
            <EmptyState icon="🔍" message="No recipes match that search." />
          ) : (
            <ul className="flex flex-col gap-2">
              {filtered.map((r) => (
                <li key={r.id}>
                  <Card className="flex items-center gap-3">
                    <Link to={`/recipes/${r.id}`} className="font-medium text-heading hover:underline">
                      {r.title}
                    </Link>
                    <span className="text-sm text-muted">{r.servings} servings</span>
                    <AddToListButton recipeId={r.id} title={r.title} onError={setError} />
                    <Button variant="link" aria-label={`Delete ${r.title}`} onClick={() => remove(r)}>
                      <TrashIcon size={18} />
                    </Button>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- RecipeList`
Expected: PASS — all existing tests plus the two new ones. (The existing "adds a recipe to the list" and delete-by-`aria-label` tests still pass because the aria-labels are unchanged.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeList.tsx frontend/src/recipes/RecipeList.test.tsx
git commit -m "feat(web): sticky search, inline Added confirmation, TrashIcon on recipes list"
```

---

### Task 2: Add recipe — URL/Manual segmented toggle

**Files:**
- Modify: `frontend/src/recipes/AddRecipe.tsx`
- Test: `frontend/src/recipes/AddRecipe.test.tsx`

Current `AddRecipe.tsx` shows two `Card`s at once (Import by URL, then Or enter manually). We add a `SegmentedControl` and render only the active mode's card. Default mode is `"url"`. All `run()`, `extract()`, validation, and navigation logic is unchanged — only field visibility is gated. Because the manual fields are now hidden by default, the existing manual/extract tests must first click the **Manual** tab.

- [ ] **Step 1: Update existing tests + add the mode-toggle test**

In `frontend/src/recipes/AddRecipe.test.tsx`, add a `Manual`-tab click before any manual-field interaction. Apply these edits:

In `"navigates to the new recipe after manual create"`, before typing into Title, add the tab click so the manual fields are visible:

```tsx
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
    await userEvent.type(screen.getByLabelText(/title/i), "Bread");
    await userEvent.type(screen.getByLabelText(/ingredients/i), "2 cups flour");
    await userEvent.click(screen.getByRole("button", { name: /save recipe/i }));
```

In `"extracts ingredients into the textarea"`, add the tab click before grabbing the textarea:

```tsx
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
    const textarea = screen.getByLabelText(/ingredients/i);
```

In `"shows an error when extraction fails"`, add the tab click before typing into ingredients:

```tsx
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
    await userEvent.type(screen.getByLabelText(/ingredients/i), "block");
```

The two URL-import tests (`"... after a successful URL import"` and `"shows an error when import fails"`) stay unchanged — URL is the default mode.

Then add this new test inside the `describe("AddRecipe", ...)` block:

```tsx
it("defaults to URL mode and toggles to manual", async () => {
  renderAddRecipe();
  expect(screen.getByLabelText(/recipe url/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/^title$/i)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
  expect(screen.getByLabelText(/^title$/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/recipe url/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- AddRecipe`
Expected: FAIL — there is no `role="tab"` named "Manual" yet, so `getByRole("tab", ...)` throws in the updated and new tests.

- [ ] **Step 3: Implement the toggle**

Replace the entire contents of `frontend/src/recipes/AddRecipe.tsx` with:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createRecipe, extractIngredients, importRecipe } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";

export function AddRecipe() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"url" | "manual">("url");
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

  async function extract() {
    setBusy(true);
    setError(null);
    try {
      const extracted = await extractIngredients(lines);
      setLines(extracted.join("\n"));
    } catch {
      setError("Couldn't extract ingredients — edit manually or try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Add recipe" />
      <SegmentedControl
        options={[
          { value: "url", label: "URL" },
          { value: "manual", label: "Manual" },
        ]}
        value={mode}
        onChange={setMode}
      />
      {error && <ErrorBanner message={error} />}

      {mode === "url" ? (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Import by URL</h3>
          <Input label="Recipe URL" value={url} onChange={(e) => setUrl(e.target.value)} />
          <Button disabled={!url} loading={busy} className="self-start" onClick={() => run(() => importRecipe(url))}>
            Import
          </Button>
        </Card>
      ) : (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Enter manually</h3>
          <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input
            label="Servings"
            type="number"
            value={servings}
            onChange={(e) => setServings(Number(e.target.value))}
          />
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor="ingredients" className="font-medium text-heading">
              Ingredients
            </label>
            <p id="ingredients-hint" className="text-xs text-muted">
              Paste a full recipe and click Extract, or enter one ingredient per line.
            </p>
            <textarea
              id="ingredients"
              aria-describedby="ingredients-hint"
              className="min-h-24 rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              value={lines}
              onChange={(e) => setLines(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={!lines.trim()}
              loading={busy}
              className="self-start"
              onClick={extract}
            >
              Extract ingredients
            </Button>
            <Button
              disabled={!title.trim() || !lines.trim()}
              loading={busy}
              className="self-start"
              onClick={() => run(() => createRecipe(title, servings, lines.split("\n")))}
            >
              Save recipe
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- AddRecipe`
Expected: PASS — URL-import tests run in default mode; manual/extract tests pass after clicking the Manual tab; the toggle test confirms the mode switch.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/AddRecipe.tsx frontend/src/recipes/AddRecipe.test.tsx
git commit -m "feat(web): URL/Manual segmented toggle on add recipe"
```

---

### Task 3: Kroger setup — explicit connection states

**Files:**
- Modify: `frontend/src/recipes/KrogerSetup.tsx`
- Test: `frontend/src/recipes/KrogerSetup.test.tsx`

Current `KrogerSetup.tsx` shows the connection as a plain `<p>Connected…</p>` or a Connect button. We make the three states explicit: a success `Pill` "Connected ✓", a warning `Pill` "Session expired" + a **Reconnect** button, or a **Connect Kroger** button. The home-store line keeps its exact "Home store: {name}" text (existing tests match it) but gains heading weight. `connect()`/`findStores()`/`choose()` and the home-store text are otherwise unchanged.

- [ ] **Step 1: Write the failing tests**

Add these two tests to `frontend/src/recipes/KrogerSetup.test.tsx` inside the `describe("KrogerSetup", ...)` block. Keep all existing tests as-is.

```tsx
it("shows a connected pill when connected and not expired", async () => {
  vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: false });
  render(<KrogerSetup />);
  expect(await screen.findByText(/connected ✓/i)).toBeInTheDocument();
});

it("shows session-expired with a reconnect button", async () => {
  vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: true });
  render(<KrogerSetup />);
  expect(await screen.findByText(/session expired/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /reconnect/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- KrogerSetup`
Expected: FAIL — there is no "Connected ✓" text, no "Session expired" text, and no Reconnect button yet (the connected state renders "Connected." plain text).

- [ ] **Step 3: Implement the connection states**

Replace the entire contents of `frontend/src/recipes/KrogerSetup.tsx` with:

```tsx
import { useEffect, useState } from "react";

import { getKrogerLoginUrl, getKrogerStatus, getMatch, searchLocations, setStore } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Pill } from "../components/ui/Pill";
import type { KrogerLocation, KrogerStatus } from "./types";

export function KrogerSetup() {
  const [status, setStatus] = useState<KrogerStatus | null>(null);
  const [zip, setZip] = useState("");
  const [stores, setStores] = useState<KrogerLocation[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getKrogerStatus().then(setStatus).catch(() => setStatus(null));
    getMatch().then((m) => setSelectedName(m.store_name ?? null)).catch(() => {});
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

  async function choose(loc: KrogerLocation) {
    const match = await setStore(loc.location_id, loc.name);
    setSelectedName(match.store_name ?? null);
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Kroger" />

      <Card className="flex flex-col gap-3">
        {status?.connected ? (
          status.expired ? (
            <div className="flex items-center gap-3">
              <Pill tone="warning">Session expired</Pill>
              <Button className="ml-auto" onClick={connect}>
                Reconnect
              </Button>
            </div>
          ) : (
            <Pill tone="success">Connected ✓</Pill>
          )
        ) : (
          <Button onClick={connect}>Connect Kroger</Button>
        )}
      </Card>

      <Card className="flex flex-col gap-3">
        <h3 className="text-lg font-semibold text-heading">Home store</h3>
        {selectedName && <p className="text-sm font-medium text-heading">Home store: {selectedName}</p>}
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
              <Button variant="secondary" className="ml-auto" onClick={() => choose(s)}>
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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- KrogerSetup`
Expected: PASS — the new connected-pill and expired/reconnect tests pass; the existing disconnected, store-search, store-select, and home-store-hydration tests still pass (the "Home store: {name}" text is unchanged).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/KrogerSetup.tsx frontend/src/recipes/KrogerSetup.test.tsx
git commit -m "feat(web): explicit Kroger connection states (connected/expired/disconnected)"
```

---

### Task 4: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: PASS — all suites green, no regressions.

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit (only if tsc/build produced incidental changes; otherwise skip)**

```bash
git status --short
# If nothing to commit, this task is complete.
```

---

## Notes for the implementer

- Backend is untouched; do not run or modify backend tests for this plan.
- Do not rename any `aria-label` (`Add <title> to list`, `Delete <title>`) or the "Home store: {name}" text — existing tests depend on them.
- `SegmentedControl`'s `onChange` is typed `(value: "url" | "manual") => void`, so passing `setMode` directly type-checks.
- The `TrashIcon` is decorative (`aria-hidden`); accessibility comes from the button's `aria-label`, which is preserved.

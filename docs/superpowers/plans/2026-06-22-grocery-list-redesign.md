# Grocery-list redesign (Items · Staples · Cart) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Grocery-list page into a segmented Items · Staples · Cart flow on the new visual foundation, with inline pantry "already have", a confirmed/needs-a-product cart with per-line remove, and a sticky "Send to cart".

**Architecture:** Add `item_id` to the list items API. Add two shared primitives (`SegmentedControl`, `CollapsibleSection`). Rewrite `GroceryList.tsx` into a segmented shell composing a new `ItemsTab` (recipes collapsible + aisle-grouped items + "Already have"), the existing `StaplesSection`, and a new `CartTab` (reworked from `MatchAndSend`). Remove `PantryCheck` (folded into Items) and `MatchAndSend` (becomes `CartTab`).

**Tech Stack:** React + TypeScript + Vite + Tailwind (vitest + Testing Library); FastAPI + Pydantic backend.

---

## Conventions

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest <args>
cd frontend && npm test -- <path>          # one file
cd frontend && npm test && npx tsc -b       # full suite + typecheck
```

---

## File Structure

- Modify `backend/app/consolidate/schemas.py` + `router.py` — `item_id` on list items.
- Modify `frontend/src/recipes/types.ts` — `ListItem.item_id`.
- Create `frontend/src/components/ui/SegmentedControl.tsx` (+ test).
- Create `frontend/src/components/ui/CollapsibleSection.tsx` (+ test).
- Create `frontend/src/recipes/ItemsTab.tsx` (+ test).
- Create `frontend/src/recipes/CartTab.tsx` (+ test); add `TrashIcon` to `components/ui/icons.tsx`.
- Rewrite `frontend/src/recipes/GroceryList.tsx`; rewrite `GroceryList.test.tsx`.
- Delete `frontend/src/recipes/MatchAndSend.tsx` + `MatchAndSend.test.tsx`, `PantryCheck.tsx` + `PantryCheck.test.tsx`.
- `StaplesSection.tsx` is reused unchanged (the foundation already retokenized it).

---

## Task 1: Backend — `item_id` on list items

**Files:**
- Modify: `backend/app/consolidate/schemas.py`
- Modify: `backend/app/consolidate/router.py`
- Modify: `frontend/src/recipes/types.ts`
- Test: `backend/tests/test_consolidate_router.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_consolidate_router.py` (it already has a helper that adds a recipe and GETs `/list`; mirror the existing item-asserting test). Add:

```python
def test_list_items_include_item_id(db_session):
    gl, ing, recipe = _seed_recipe_on_list(db_session)
    client = _client(db_session)
    body = client.get("/list").json()
    assert isinstance(body["items"][0]["item_id"], int)
    app.dependency_overrides.clear()
```

If the existing helper/fixtures in this file have different names, reuse whatever the existing "adds a recipe then GETs /list and asserts items[0]" test uses (e.g. its seeding helper + `_client`); the only new assertion is `isinstance(body["items"][0]["item_id"], int)`.

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_consolidate_router.py -k item_id -v
```
Expected: FAIL (KeyError — no `item_id`).

- [ ] **Step 3: Add the field**

In `backend/app/consolidate/schemas.py`, add `item_id: int` as the first field of `ListItemRead`:

```python
class ListItemRead(BaseModel):
    item_id: int
    ingredient_id: int
    ingredient_name: str | None
    category: str | None
    quantities: list[SubQuantity]
    source_recipe_ids: list[int]
    pantry_status: str
```

In `backend/app/consolidate/router.py` `_serialize`, set `item_id=r.id` in the `ListItemRead(...)` constructor (add it as the first kwarg; `r` is the `GroceryListItem`).

- [ ] **Step 4: Add the frontend type field**

In `frontend/src/recipes/types.ts`, add `item_id: number;` as the first field of `ListItem`.

- [ ] **Step 5: Run to verify**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_consolidate_router.py -v
cd frontend && npx tsc -b
```
Expected: backend tests pass; frontend typecheck clean. (Frontend test fixtures that build a `ListItem` without `item_id` will be updated in later tasks where they're used; `tsc` may flag them — if so, add `item_id` to those literal fixtures, e.g. in `GroceryList.test.tsx`. It's fine to add the field to fixtures now.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/consolidate/schemas.py backend/app/consolidate/router.py backend/tests/test_consolidate_router.py frontend/src/recipes/types.ts
git commit -m "feat(list): expose item_id on grocery list items"
```

---

## Task 2: SegmentedControl

**Files:**
- Create: `frontend/src/components/ui/SegmentedControl.tsx`
- Test: `frontend/src/components/ui/SegmentedControl.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/ui/SegmentedControl.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SegmentedControl } from "./SegmentedControl";

afterEach(() => vi.restoreAllMocks());

const opts = [
  { value: "items", label: "Items" },
  { value: "cart", label: "Cart" },
] as const;

describe("SegmentedControl", () => {
  it("marks the active option and fires onChange", async () => {
    const onChange = vi.fn();
    render(<SegmentedControl options={[...opts]} value="items" onChange={onChange} />);
    expect(screen.getByRole("tab", { name: "Items" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Cart" })).toHaveAttribute("aria-selected", "false");
    await userEvent.click(screen.getByRole("tab", { name: "Cart" }));
    expect(onChange).toHaveBeenCalledWith("cart");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- src/components/ui/SegmentedControl.test.tsx
```
Expected: FAIL (module missing).

- [ ] **Step 3: Create the component**

Create `frontend/src/components/ui/SegmentedControl.tsx`:

```tsx
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div role="tablist" className="flex gap-1 rounded-xl bg-line p-1">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={`min-h-[40px] flex-1 rounded-lg text-sm font-semibold transition-colors ${
              active ? "bg-surface text-heading shadow-[0_1px_2px_rgba(16,24,40,0.06)]" : "text-muted"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify + typecheck**

```bash
cd frontend && npm test -- src/components/ui/SegmentedControl.test.tsx && npx tsc -b
```
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/SegmentedControl.tsx frontend/src/components/ui/SegmentedControl.test.tsx
git commit -m "feat(ui): SegmentedControl"
```

---

## Task 3: CollapsibleSection

**Files:**
- Create: `frontend/src/components/ui/CollapsibleSection.tsx`
- Test: `frontend/src/components/ui/CollapsibleSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/ui/CollapsibleSection.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CollapsibleSection } from "./CollapsibleSection";

afterEach(() => vi.restoreAllMocks());

describe("CollapsibleSection", () => {
  it("is collapsed by default and toggles open", async () => {
    render(
      <CollapsibleSection title="On this list">
        <p>body content</p>
      </CollapsibleSection>,
    );
    const toggle = screen.getByRole("button", { name: /on this list/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("body content")).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("body content")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- src/components/ui/CollapsibleSection.test.tsx
```
Expected: FAIL (module missing).

- [ ] **Step 3: Create the component**

Create `frontend/src/components/ui/CollapsibleSection.tsx`:

```tsx
import { useState } from "react";

export function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-2xl border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-[44px] w-full items-center justify-between px-4 py-3 text-sm font-semibold text-heading"
      >
        <span>{title}</span>
        <span className={`text-muted transition-transform ${open ? "rotate-90" : ""}`} aria-hidden="true">
          ›
        </span>
      </button>
      {open && <div className="border-t border-line px-4 py-3">{children}</div>}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify + typecheck**

```bash
cd frontend && npm test -- src/components/ui/CollapsibleSection.test.tsx && npx tsc -b
```
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/CollapsibleSection.tsx frontend/src/components/ui/CollapsibleSection.test.tsx
git commit -m "feat(ui): CollapsibleSection"
```

---

## Task 4: ItemsTab

**Files:**
- Create: `frontend/src/recipes/ItemsTab.tsx`
- Test: `frontend/src/recipes/ItemsTab.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/recipes/ItemsTab.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ItemsTab } from "./ItemsTab";
import type { GroceryListData } from "./types";

afterEach(() => vi.restoreAllMocks());

const list: GroceryListData = {
  id: 1,
  status: "draft",
  recipes: [
    { recipe_id: 9, title: "Pancakes", servings: 4, default_servings: 2 },
    { recipe_id: 10, title: "Soup", servings: 2, default_servings: 2 },
  ],
  items: [
    { item_id: 100, ingredient_id: 5, ingredient_name: "flour", category: "baking", quantities: [{ qty: 3, unit: "cup" }], source_recipe_ids: [9, 10], pantry_status: "needed" },
    { item_id: 101, ingredient_id: 6, ingredient_name: "garlic", category: "produce", quantities: [{ qty: 2, unit: "clove" }], source_recipe_ids: [10], pantry_status: "skipped" },
  ],
};

describe("ItemsTab", () => {
  it("shows items with consolidated amount and multi-recipe source", async () => {
    render(<ItemsTab list={list} reload={vi.fn()} />);
    expect(screen.getByText("flour")).toBeInTheDocument();
    expect(screen.getByText(/3 cup/)).toBeInTheDocument();
    expect(screen.getByText(/from 2 recipes/i)).toBeInTheDocument();
  });

  it("marks an item already-have via setPantryDecision and reloads", async () => {
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    const reload = vi.fn();
    render(<ItemsTab list={list} reload={reload} />);
    await userEvent.click(screen.getByRole("button", { name: /already have flour/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(100, false));
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  it("can undo a skipped item", async () => {
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    render(<ItemsTab list={list} reload={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /undo garlic/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(101, true));
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- src/recipes/ItemsTab.test.tsx
```
Expected: FAIL (module missing).

- [ ] **Step 3: Create the component**

Create `frontend/src/recipes/ItemsTab.tsx`:

```tsx
import { useState } from "react";

import { removeRecipeFromList, setPantryDecision, updateListServings } from "../api";
import { Button } from "../components/ui/Button";
import { CollapsibleSection } from "../components/ui/CollapsibleSection";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import type { GroceryListData, ListItem, ListRecipe, SubQuantity } from "./types";

function formatQuantities(quantities: SubQuantity[]): string {
  if (quantities.length === 0) return "";
  return quantities
    .map((q) =>
      q.qty === null ? `as needed${q.unit ? ` (${q.unit})` : ""}` : `${q.qty}${q.unit ? ` ${q.unit}` : ""}`,
    )
    .join(" + ");
}

function sourceLabel(item: ListItem, titleById: Record<number, string>): string {
  const titles = item.source_recipe_ids.map((id) => titleById[id]).filter(Boolean);
  if (titles.length === 0) return "";
  if (titles.length <= 2) return `from ${titles.join(" + ")}`;
  return `from ${titles.length} recipes`;
}

function RecipeRow({ recipe, reload }: { recipe: ListRecipe; reload: () => void }) {
  const [servings, setServings] = useState(recipe.servings.toString());

  async function update() {
    const n = Number(servings);
    if (servings.trim() === "" || !Number.isFinite(n)) return;
    await updateListServings(recipe.recipe_id, n);
    reload();
  }

  return (
    <li className="flex flex-wrap items-end gap-2">
      <span className="font-medium text-heading">{recipe.title}</span>
      <Input
        label={`Servings for ${recipe.title}`}
        value={servings}
        onChange={(e) => setServings(e.target.value)}
        className="w-20"
      />
      <Button variant="secondary" aria-label={`Update ${recipe.title}`} onClick={update}>
        Update
      </Button>
      <Button
        variant="link"
        aria-label={`Remove ${recipe.title}`}
        onClick={async () => {
          await removeRecipeFromList(recipe.recipe_id);
          reload();
        }}
      >
        Remove
      </Button>
    </li>
  );
}

export function ItemsTab({ list, reload }: { list: GroceryListData; reload: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const titleById = Object.fromEntries(list.recipes.map((r) => [r.recipe_id, r.title]));

  async function decide(itemId: number, keep: boolean) {
    setError(null);
    try {
      await setPantryDecision(itemId, keep);
      reload();
    } catch {
      setError("Couldn't update that item — please try again.");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <ErrorBanner message={error} />}

      <CollapsibleSection title={`On this list · ${list.recipes.length} recipe${list.recipes.length === 1 ? "" : "s"}`}>
        <ul className="flex flex-col gap-3">
          {list.recipes.map((r) => (
            <RecipeRow key={r.recipe_id} recipe={r} reload={reload} />
          ))}
        </ul>
      </CollapsibleSection>

      <ul className="flex flex-col gap-2">
        {list.items.map((item, idx) => {
          const prev = list.items[idx - 1];
          const showCat = item.category && item.category !== prev?.category;
          const skipped = item.pantry_status === "skipped";
          return (
            <li key={item.item_id}>
              {showCat && (
                <p className="mb-1 mt-2 text-xs font-bold uppercase tracking-wide text-muted">{item.category}</p>
              )}
              <div
                className={`flex items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-3 ${
                  skipped ? "opacity-50" : ""
                }`}
              >
                <div className="min-w-0">
                  <p className="font-semibold text-heading">{item.ingredient_name}</p>
                  <p className="text-sm text-muted">
                    {skipped ? "skipped — you have it" : formatQuantities(item.quantities)}
                  </p>
                  {!skipped && sourceLabel(item, titleById) && (
                    <p className="text-xs text-muted">{sourceLabel(item, titleById)}</p>
                  )}
                  {item.pantry_status === "maybe_have" && (
                    <p className="text-xs text-warning">bought recently — already have?</p>
                  )}
                </div>
                {skipped ? (
                  <Button variant="link" aria-label={`Undo ${item.ingredient_name}`} onClick={() => decide(item.item_id, true)}>
                    Undo
                  </Button>
                ) : (
                  <Button
                    variant="link"
                    aria-label={`Already have ${item.ingredient_name}`}
                    onClick={() => decide(item.item_id, false)}
                  >
                    Already have
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify + typecheck**

```bash
cd frontend && npm test -- src/recipes/ItemsTab.test.tsx && npx tsc -b
```
Expected: PASS (3 tests), clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/ItemsTab.tsx frontend/src/recipes/ItemsTab.test.tsx
git commit -m "feat(web): ItemsTab — aisle-grouped items, recipes collapsible, already-have"
```

---

## Task 5: CartTab (rework MatchAndSend)

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx` (add `TrashIcon`)
- Create: `frontend/src/recipes/CartTab.tsx`
- Test: `frontend/src/recipes/CartTab.test.tsx`
- Delete: `frontend/src/recipes/MatchAndSend.tsx`, `frontend/src/recipes/MatchAndSend.test.tsx`, `frontend/src/recipes/PantryCheck.tsx`, `frontend/src/recipes/PantryCheck.test.tsx`

- [ ] **Step 1: Add TrashIcon**

In `frontend/src/components/ui/icons.tsx`, add (after `CloseIcon`):

```tsx
export const TrashIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 7h16M9 7V5h6v2M7 7l1 12h8l1-12" />
  </Svg>
);
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/recipes/CartTab.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ApiError } from "../api";
import { CartTab } from "./CartTab";

afterEach(() => vi.restoreAllMocks());

const baseMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    { item_id: 1, ingredient_id: 2, ingredient_name: "flour", total_qty: 3, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: "0001", current: { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" } },
    { item_id: 2, ingredient_id: 3, ingredient_name: "milk", total_qty: 1, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: null, current: null },
  ],
};

describe("CartTab", () => {
  it("splits confirmed and needs-a-product", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    render(<CartTab />);
    expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
    expect(screen.getByText(/confirmed/i)).toBeInTheDocument();
    expect(screen.getByText(/needs a product/i)).toBeInTheDocument();
  });

  it("removes an item via setPantryDecision and refetches", async () => {
    const getMatch = vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    render(<CartTab />);
    await screen.findByText(/AP Flour/);
    await userEvent.click(screen.getByRole("button", { name: /remove flour/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(1, false));
    await waitFor(() => expect(getMatch).toHaveBeenCalledTimes(2));
  });

  it("sends the cart", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const send = vi.spyOn(api, "sendCart").mockResolvedValue({ status: "sent_to_kroger", results: [{ upc: "0001", ok: true, error: null }] });
    render(<CartTab />);
    await screen.findByText(/AP Flour/);
    await userEvent.click(screen.getByRole("button", { name: /send to cart/i }));
    await waitFor(() => expect(send).toHaveBeenCalledWith("PICKUP"));
  });

  it("prompts reconnect on 409", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    vi.spyOn(api, "sendCart").mockRejectedValue(new ApiError(409));
    render(<CartTab />);
    await screen.findByText(/AP Flour/);
    await userEvent.click(screen.getByRole("button", { name: /send to cart/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reconnect/i);
  });
});
```

- [ ] **Step 3: Run to verify it fails**

```bash
cd frontend && npm test -- src/recipes/CartTab.test.tsx
```
Expected: FAIL (module missing).

- [ ] **Step 4: Create CartTab**

Create `frontend/src/recipes/CartTab.tsx`:

```tsx
import { useEffect, useState } from "react";

import { ApiError, confirmProduct, getMatch, sendCart, setPantryDecision } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import { TrashIcon } from "../components/ui/icons";
import { ProductPickerModal } from "./ProductPickerModal";
import type { MatchData, MatchItem, ProductChoice, SendResult } from "./types";

export function CartTab() {
  const [match, setMatch] = useState<MatchData | null>(null);
  const [openItem, setOpenItem] = useState<MatchItem | null>(null);
  const [modality, setModality] = useState("PICKUP");
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getMatch().then(setMatch).catch(() => setMatch(null));
  }
  useEffect(load, []);

  function report(err: unknown) {
    setError(
      err instanceof ApiError && err.status === 409
        ? "Your Kroger session expired — reconnect on the Kroger tab, then try again."
        : "Something went wrong talking to Kroger. Please try again.",
    );
  }

  async function pick(product: ProductChoice) {
    if (openItem === null) return;
    setError(null);
    try {
      setMatch(
        await confirmProduct(openItem.item_id, {
          kroger_upc: product.upc,
          kroger_description: product.description,
          package_size: product.size,
        }),
      );
    } catch (err) {
      report(err);
    } finally {
      setOpenItem(null);
    }
  }

  async function remove(item: MatchItem) {
    setError(null);
    try {
      await setPantryDecision(item.item_id, false);
      load();
    } catch (err) {
      report(err);
    }
  }

  async function send() {
    setError(null);
    try {
      setSendResult(await sendCart(modality));
      load();
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

  const confirmed = match.items.filter((it) => it.current !== null);
  const needs = match.items.filter((it) => it.current === null);

  function row(it: MatchItem) {
    return (
      <li key={it.item_id} className="flex items-start justify-between gap-3 rounded-2xl border border-line bg-surface p-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-semibold text-heading">
            {it.ingredient_name}
            {it.current && <span className="text-success" aria-hidden="true">✓</span>}
            {it.purchase_qty_estimated && <Pill tone="warning">Check qty</Pill>}
          </p>
          {it.current ? (
            <p className="text-sm text-muted">
              {it.current.description}
              {it.current.size ? ` (${it.current.size})` : ""} · buy {it.purchase_qty}
            </p>
          ) : (
            <p className="text-sm text-muted">need {it.total_qty ?? "?"} {it.total_unit ?? ""}</p>
          )}
          <Button variant="link" className="px-0" onClick={() => setOpenItem(it)}>
            {it.current ? "Change" : "Choose product →"}
          </Button>
        </div>
        <button
          type="button"
          aria-label={`Remove ${it.ingredient_name}`}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-danger"
          onClick={() => remove(it)}
        >
          <TrashIcon size={18} />
        </button>
      </li>
    );
  }

  return (
    <Card className="flex flex-col gap-3">
      {error && <ErrorBanner message={error} />}
      {!match.connected && <p className="text-sm text-muted">Connect your Kroger account first.</p>}
      {!match.store_location_id && <p className="text-sm text-muted">Pick a home store first.</p>}

      {confirmed.length > 0 && (
        <>
          <p className="text-xs font-bold uppercase tracking-wide text-muted">Confirmed · {confirmed.length}</p>
          <ul className="flex flex-col gap-2">{confirmed.map(row)}</ul>
        </>
      )}
      {needs.length > 0 && (
        <>
          <p className="text-xs font-bold uppercase tracking-wide text-muted">Needs a product · {needs.length}</p>
          <ul className="flex flex-col gap-2">{needs.map(row)}</ul>
        </>
      )}
      {match.items.length === 0 && <p className="text-sm text-muted">Nothing to send yet.</p>}

      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Fulfillment</span>
          <select
            className="min-h-[44px] rounded-lg border border-line-strong bg-surface px-3 py-2 text-ink"
            value={modality}
            onChange={(e) => setModality(e.target.value)}
          >
            <option value="PICKUP">Pickup</option>
            <option value="DELIVERY">Delivery</option>
          </select>
        </label>
        <Button className="ml-auto" onClick={send}>
          Send to cart
        </Button>
      </div>

      {sendResult && (
        <div className="rounded-xl bg-canvas p-3">
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

      {openItem && (
        <ProductPickerModal
          key={openItem.item_id}
          itemId={openItem.item_id}
          ingredientName={openItem.ingredient_name}
          onChoose={pick}
          onClose={() => setOpenItem(null)}
        />
      )}
    </Card>
  );
}
```

- [ ] **Step 5: Delete the replaced files**

```bash
cd frontend && rm src/recipes/MatchAndSend.tsx src/recipes/MatchAndSend.test.tsx src/recipes/PantryCheck.tsx src/recipes/PantryCheck.test.tsx
```

(They're replaced by `CartTab` and `ItemsTab`. `GroceryList.tsx` still imports them until Task 6 — that's fine because Task 5 and Task 6 are committed together is NOT assumed; to keep this task's suite green, the next step builds CartTab's test in isolation. The full suite is run after Task 6 wires the shell. Run only the new file here.)

- [ ] **Step 6: Run the CartTab test + typecheck the new file's deps**

```bash
cd frontend && npm test -- src/recipes/CartTab.test.tsx
```
Expected: PASS (4 tests). Do NOT run the full suite yet (GroceryList.tsx still references the deleted MatchAndSend/PantryCheck and won't typecheck until Task 6). `npx tsc -b` will fail until Task 6 — that is expected and resolved there.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/icons.tsx frontend/src/recipes/CartTab.tsx frontend/src/recipes/CartTab.test.tsx
git add -A frontend/src/recipes/MatchAndSend.tsx frontend/src/recipes/MatchAndSend.test.tsx frontend/src/recipes/PantryCheck.tsx frontend/src/recipes/PantryCheck.test.tsx
git commit -m "feat(web): CartTab (confirmed/needs-product, remove, send); drop MatchAndSend/PantryCheck"
```

---

## Task 6: GroceryList segmented shell

**Files:**
- Modify: `frontend/src/recipes/GroceryList.tsx` (rewrite)
- Test: `frontend/src/recipes/GroceryList.test.tsx` (rewrite)

- [ ] **Step 1: Rewrite the test**

Replace `frontend/src/recipes/GroceryList.test.tsx` with:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { GroceryList } from "./GroceryList";

beforeEach(() => {
  vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
  vi.spyOn(api, "getStaples").mockResolvedValue({ staples: [] });
});
afterEach(() => vi.restoreAllMocks());

const list = {
  id: 1,
  status: "draft",
  recipes: [{ recipe_id: 9, title: "Pancakes", servings: 4, default_servings: 2 }],
  items: [
    { item_id: 100, ingredient_id: 5, ingredient_name: "flour", category: "baking", quantities: [{ qty: 3, unit: "cup" }], source_recipe_ids: [9], pantry_status: "needed" },
  ],
};

describe("GroceryList", () => {
  it("shows the Items tab with consolidated items by default", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    expect(await screen.findByText("flour")).toBeInTheDocument();
  });

  it("empty state when no recipes", async () => {
    vi.spyOn(api, "getList").mockResolvedValue({ id: 1, status: "draft", recipes: [], items: [] });
    render(<GroceryList />);
    expect(await screen.findByText(/no recipes on your list/i)).toBeInTheDocument();
  });

  it("switches to the Cart tab", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    await screen.findByText("flour");
    await userEvent.click(screen.getByRole("tab", { name: /cart/i }));
    await waitFor(() => expect(api.getMatch).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- src/recipes/GroceryList.test.tsx
```
Expected: FAIL (old shell, no tabs).

- [ ] **Step 3: Rewrite GroceryList**

Replace `frontend/src/recipes/GroceryList.tsx` with:

```tsx
import { useEffect, useState } from "react";

import { getList } from "../api";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { Spinner } from "../components/ui/Spinner";
import { CartTab } from "./CartTab";
import { ItemsTab } from "./ItemsTab";
import { StaplesSection } from "./StaplesSection";
import type { GroceryListData } from "./types";

type Tab = "items" | "staples" | "cart";

export function GroceryList() {
  const [list, setList] = useState<GroceryListData | null>(null);
  const [tab, setTab] = useState<Tab>("items");

  function reload() {
    getList().then(setList).catch(() => setList(null));
  }
  useEffect(reload, []);

  if (list === null)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );

  if (list.recipes.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader title="Grocery list" />
        <EmptyState icon="🧺" message="No recipes on your list yet. Add some from the Recipes tab." />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Grocery list" />
      <SegmentedControl
        options={[
          { value: "items", label: "Items" },
          { value: "staples", label: "Staples" },
          { value: "cart", label: "Cart" },
        ]}
        value={tab}
        onChange={(t) => {
          if (t === "items") reload();
          setTab(t);
        }}
      />
      {tab === "items" && <ItemsTab list={list} reload={reload} />}
      {tab === "staples" && <StaplesSection onChange={reload} />}
      {tab === "cart" && <CartTab />}
    </div>
  );
}
```

- [ ] **Step 4: Run the full suite + typecheck + build**

```bash
cd frontend && npm test 2>&1 | tail -4 && npx tsc -b && npm run build 2>&1 | tail -3
```
Expected: all pass; typecheck clean (the deleted MatchAndSend/PantryCheck are no longer referenced); build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/GroceryList.tsx frontend/src/recipes/GroceryList.test.tsx
git commit -m "feat(web): segmented Grocery list (Items/Staples/Cart)"
```

---

## Task 7: Full verification

- [ ] **Step 1: Backend suite**

```bash
cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest -q
```
Expected: all pass.

- [ ] **Step 2: Frontend suite + typecheck + build**

```bash
cd frontend && npm test && npx tsc -b && npm run build
```
Expected: all pass; no references to the deleted `MatchAndSend`/`PantryCheck` remain (`grep -rn "MatchAndSend\|PantryCheck" src` → nothing).

- [ ] **Step 3: Manual smoke (optional)**

Open the Grocery list on a phone viewport: the **Items** tab shows aisle-grouped consolidated items with a collapsible "On this list" recipes section and "Already have"; **Staples** toggles; **Cart** shows confirmed vs needs-a-product with a trash remove + "Send to cart". Mark "Already have", switch to Cart, confirm it's gone; remove on Cart, return to Items, confirm it's greyed.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** item_id (T1); SegmentedControl (T2); CollapsibleSection (T3); ItemsTab w/ recipes collapsible + aisle grouping + already-have + maybe_have hint + source names (T4); CartTab confirmed/needs-product + remove + send + 409 (T5, reuses ProductPickerModal); segmented shell + cross-tab reload on entering Items (T6). PantryCheck folded into ItemsTab; MatchAndSend → CartTab (deleted).
- **Type/signature consistency:** `ItemsTab({ list, reload })`, `CartTab()` (self-fetching), `SegmentedControl<T>({options,value,onChange})`, `CollapsibleSection({title,defaultOpen,children})`. `setPantryDecision(itemId, keep)` used by both tabs; `item_id` present on `ListItem` (T1) and `MatchItem` (existing).
- **Deferred:** per-recipe amount breakdown (names only). Items shows the *need* (quantities); buy qty appears on Cart (from match).
- **Sequencing caveat (T5):** deleting MatchAndSend/PantryCheck makes the old `GroceryList.tsx` not typecheck until T6 rewires it; that's why T5 runs only the CartTab test and T6 runs the full suite/build.
```

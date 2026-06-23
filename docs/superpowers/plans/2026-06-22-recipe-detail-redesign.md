# Recipe-detail redesign (needs-review / tap-to-edit) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the Recipe-detail page so needs-review rows are surfaced and open, reviewed rows collapse behind a disclosure, and each row is tap-to-edit.

**Architecture:** Frontend-only rewrite of `RecipeDetail.tsx`: partition ingredients into needs-review (rendered open) and reviewed (inside a lightweight disclosure, auto-open only when nothing needs review); the `Row` becomes a tap-to-edit card (collapsed summary → expanded editor with Change/Amount/Unit/Save/Delete). Reuses `IngredientPicker`. No backend changes.

**Tech Stack:** React + TypeScript + Vite + Tailwind (vitest + Testing Library).

---

## Conventions

```bash
cd frontend && npm test -- src/recipes/RecipeDetail.test.tsx   # this component
cd frontend && npm test && npx tsc -b && npm run build          # full
```

---

## Task 1: Rework RecipeDetail (tap-to-edit + needs-review grouping)

**Files:**
- Modify: `frontend/src/recipes/RecipeDetail.tsx` (rewrite)
- Test: `frontend/src/recipes/RecipeDetail.test.tsx` (rewrite)

- [ ] **Step 1: Rewrite the test**

Replace `frontend/src/recipes/RecipeDetail.test.tsx` with:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
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

function showFetch() {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify(recipe), { status: 200 }));
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
}
function showApi(r = recipe) {
  vi.spyOn(api, "getRecipe").mockResolvedValue(r);
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
}

describe("RecipeDetail", () => {
  it("renders the recipe title", async () => {
    showFetch();
    expect(await screen.findByRole("heading", { name: /pancakes/i })).toBeInTheDocument();
  });

  it("shows the reviewed status", async () => {
    showFetch();
    expect(await screen.findByText(/all items reviewed/i)).toBeInTheDocument();
  });

  it("shows the count and opens needs-review rows by default", async () => {
    showApi({ ...recipe, ingredients: [{ ...recipe.ingredients[0], needs_review: true }] });
    expect(await screen.findByText(/1 item needs review/i)).toBeInTheDocument();
    // a needs-review row is open: its Save is visible without tapping
    expect(screen.getByRole("button", { name: /save 2 cups flour/i })).toBeInTheDocument();
  });

  it("collapses reviewed rows; tap to edit, then save", async () => {
    const update = vi.spyOn(api, "updateIngredient").mockResolvedValue(recipe);
    showApi();
    await screen.findByText("2 cups flour");
    expect(screen.queryByRole("button", { name: /save 2 cups flour/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /edit 2 cups flour/i }));
    expect(screen.getByText("Matched to:")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /save 2 cups flour/i }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, 10, { qty: 2, unit: "cup" }));
  });

  it("re-maps the ingredient via the picker", async () => {
    vi.spyOn(api, "searchIngredients").mockResolvedValue([{ id: 8, canonical_name: "garlic powder" }]);
    const update = vi.spyOn(api, "updateIngredient").mockResolvedValue(recipe);
    showApi();
    await userEvent.click(await screen.findByRole("button", { name: /edit 2 cups flour/i }));
    await userEvent.click(screen.getByRole("button", { name: /change match for 2 cups flour/i }));
    await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "gar");
    await userEvent.click(await screen.findByRole("button", { name: "garlic powder" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, 10, { ingredient_id: 8 }));
  });

  it("adds an ingredient via the add form", async () => {
    const add = vi.spyOn(api, "addIngredient").mockResolvedValue({
      ...recipe,
      ingredients: [
        ...recipe.ingredients,
        { id: 11, raw_text: "2 cloves garlic", qty: 2, unit: "clove", ingredient_id: 6, ingredient_name: "garlic", parse_source: "manual", needs_review: false },
      ],
    });
    showApi();
    await screen.findByText("2 cups flour");
    await userEvent.type(screen.getByRole("textbox", { name: /add an ingredient/i }), "2 cloves garlic");
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    await waitFor(() => expect(add).toHaveBeenCalledWith(1, "2 cloves garlic"));
    expect(await screen.findByText("2 cloves garlic")).toBeInTheDocument();
  });

  it("deletes an ingredient after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const del = vi.spyOn(api, "deleteIngredient").mockResolvedValue({ ...recipe, ingredients: [] });
    showApi();
    await userEvent.click(await screen.findByRole("button", { name: /edit 2 cups flour/i }));
    await userEvent.click(screen.getByRole("button", { name: /delete 2 cups flour/i }));
    await waitFor(() => expect(del).toHaveBeenCalledWith(1, 10));
    expect(screen.queryByText("2 cups flour")).not.toBeInTheDocument();
  });

  it("does not delete when confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const del = vi.spyOn(api, "deleteIngredient");
    showApi();
    await userEvent.click(await screen.findByRole("button", { name: /edit 2 cups flour/i }));
    await userEvent.click(screen.getByRole("button", { name: /delete 2 cups flour/i }));
    expect(del).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npm test -- src/recipes/RecipeDetail.test.tsx
```
Expected: FAIL (no "Edit <raw>" toggle; reviewed editor not collapsed).

- [ ] **Step 3: Rewrite the component**

Replace `frontend/src/recipes/RecipeDetail.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { addIngredient, deleteIngredient, getRecipe, updateIngredient } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import { IngredientPicker } from "./IngredientPicker";
import type { IngredientRead, RecipeRead } from "./types";

function Row({
  recipeId,
  ingredient,
  defaultOpen,
  onSaved,
}: {
  recipeId: number;
  ingredient: IngredientRead;
  defaultOpen: boolean;
  onSaved: (recipe: RecipeRead) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [qty, setQty] = useState(ingredient.qty?.toString() ?? "");
  const [unit, setUnit] = useState(ingredient.unit ?? "");
  const [changing, setChanging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setQty(ingredient.qty?.toString() ?? "");
    setUnit(ingredient.unit ?? "");
  }, [ingredient.qty, ingredient.unit]);

  async function save() {
    setError(null);
    try {
      onSaved(
        await updateIngredient(recipeId, ingredient.id, {
          qty: qty === "" ? undefined : Number(qty),
          unit: unit === "" ? undefined : unit,
        }),
      );
    } catch {
      setError("Couldn't save — please try again.");
    }
  }

  async function remap(ingredientId: number) {
    setError(null);
    try {
      onSaved(await updateIngredient(recipeId, ingredient.id, { ingredient_id: ingredientId }));
      setChanging(false);
    } catch {
      setError("Couldn't update the match — please try again.");
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${ingredient.raw_text}"?`)) return;
    setError(null);
    try {
      onSaved(await deleteIngredient(recipeId, ingredient.id));
    } catch {
      setError("Couldn't delete — please try again.");
    }
  }

  const amount =
    ingredient.qty != null ? ` · ${ingredient.qty}${ingredient.unit ? ` ${ingredient.unit}` : ""}` : "";

  return (
    <Card className={ingredient.needs_review ? "border-warning/40 bg-warning-tint" : ""}>
      {error && <ErrorBanner message={error} />}
      <button
        type="button"
        aria-expanded={open}
        aria-label={`Edit ${ingredient.raw_text}`}
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-[44px] w-full items-center gap-3 text-left"
      >
        <span className="min-w-0">
          <span className="flex items-center gap-2 font-medium text-heading">
            {ingredient.raw_text}
            {ingredient.needs_review && <Pill tone="warning">Needs review</Pill>}
          </span>
          <span className="block text-sm text-muted">
            → {ingredient.ingredient_name ?? "—"}
            {amount}
          </span>
        </span>
        <span className={`ml-auto text-muted transition-transform ${open ? "rotate-90" : ""}`} aria-hidden="true">
          ›
        </span>
      </button>

      {open && (
        <div className="mt-3 flex flex-col gap-3 border-t border-line pt-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted">Matched to:</span>
            <strong className="text-heading">{ingredient.ingredient_name ?? "—"}</strong>
            <Button
              variant="link"
              className="ml-auto"
              aria-label={`Change match for ${ingredient.raw_text}`}
              onClick={() => setChanging((c) => !c)}
            >
              Change
            </Button>
          </div>
          {changing && <IngredientPicker onPick={remap} />}
          <div className="flex flex-wrap items-end gap-3">
            <Input label="Amount" value={qty} onChange={(e) => setQty(e.target.value)} className="w-24" />
            <Input label="Unit" value={unit} onChange={(e) => setUnit(e.target.value)} className="w-28" />
            <Button variant="secondary" aria-label={`Save ${ingredient.raw_text}`} onClick={save}>
              Save
            </Button>
            <Button variant="link" className="text-danger" aria-label={`Delete ${ingredient.raw_text}`} onClick={remove}>
              Delete
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function ReviewedSection({
  count,
  defaultOpen,
  children,
}: {
  count: number;
  defaultOpen: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-[44px] items-center gap-2 text-sm font-semibold text-heading"
      >
        Reviewed · {count}
        <span className={`text-muted transition-transform ${open ? "rotate-90" : ""}`} aria-hidden="true">
          ›
        </span>
      </button>
      {open && <ul className="flex flex-col gap-3">{children}</ul>}
    </div>
  );
}

export function RecipeDetail() {
  const { id } = useParams();
  const recipeId = Number(id);
  const [recipe, setRecipe] = useState<RecipeRead | null>(null);
  const [newLine, setNewLine] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  useEffect(() => {
    getRecipe(recipeId).then(setRecipe).catch(() => setRecipe(null));
  }, [recipeId]);

  async function add() {
    const text = newLine.trim();
    if (!text) return;
    setAddError(null);
    try {
      setRecipe(await addIngredient(recipeId, text));
      setNewLine("");
    } catch {
      setAddError("Couldn't add that ingredient — please try again.");
    }
  }

  if (recipe === null)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );

  const needsReview = recipe.ingredients.filter((i) => i.needs_review);
  const reviewed = recipe.ingredients.filter((i) => !i.needs_review);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={recipe.title} />
      <p role="status" className="text-sm text-muted">
        {needsReview.length > 0
          ? `${needsReview.length} item${needsReview.length === 1 ? "" : "s"} need${needsReview.length === 1 ? "s" : ""} review`
          : "All items reviewed ✓"}
      </p>
      <p className="text-sm text-muted">Tap a line to fix its amount or matched ingredient.</p>

      {needsReview.length > 0 && (
        <ul className="flex flex-col gap-3">
          {needsReview.map((ing) => (
            <li key={ing.id}>
              <Row recipeId={recipe.id} ingredient={ing} defaultOpen onSaved={setRecipe} />
            </li>
          ))}
        </ul>
      )}

      {reviewed.length > 0 && (
        <ReviewedSection count={reviewed.length} defaultOpen={needsReview.length === 0}>
          {reviewed.map((ing) => (
            <li key={ing.id}>
              <Row recipeId={recipe.id} ingredient={ing} defaultOpen={false} onSaved={setRecipe} />
            </li>
          ))}
        </ReviewedSection>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
        className="mt-2 flex items-end gap-2"
      >
        <Input
          label="Add an ingredient"
          placeholder="e.g. 2 cloves garlic"
          value={newLine}
          onChange={(e) => setNewLine(e.target.value)}
          className="w-full"
        />
        <Button type="submit" disabled={!newLine.trim()}>
          Add
        </Button>
      </form>
      {addError && <ErrorBanner message={addError} />}
    </div>
  );
}
```

- [ ] **Step 4: Run the test + typecheck**

```bash
cd frontend && npm test -- src/recipes/RecipeDetail.test.tsx && npx tsc -b
```
Expected: PASS (8 tests), clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/recipes/RecipeDetail.tsx frontend/src/recipes/RecipeDetail.test.tsx
git commit -m "feat(web): recipe detail — needs-review grouping + tap-to-edit rows"
```

---

## Task 2: Full verification

- [ ] **Step 1: Full frontend suite + typecheck + build**

```bash
cd frontend && npm test && npx tsc -b && npm run build
```
Expected: all pass; build clean. (Backend untouched.)

- [ ] **Step 2: Manual smoke (optional)**

Open a recipe with a mix of flagged and clean ingredients on a phone viewport: needs-review rows are at top, amber, open for editing; reviewed rows sit under a "Reviewed · N" disclosure (open automatically when nothing needs review). Tap a collapsed row to reveal its editor; Save / Change / Delete work; the inline "Add an ingredient" still adds. Saving a flagged row moves it into Reviewed.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** needs-review/reviewed partition + grouping (RecipeDetail); needs-review rows open by default; reviewed under a lightweight disclosure auto-open when `needsReview.length === 0`; tap-to-edit `Row` (collapsed summary → editor with Change/Amount/Unit/Save/Delete); inline add unchanged; reuse `IngredientPicker`; no backend changes.
- **Accessible-name design (so tests are unambiguous):** the summary toggle is `aria-label="Edit <raw_text>"`; Save is `Save <raw_text>`; Delete `Delete <raw_text>`; Change `Change match for <raw_text>` — all distinct, so role/name queries don't collide when a row is expanded.
- **State note:** the `Row` re-syncs local `qty`/`unit` from props via `useEffect` (so a server-normalized unit, e.g. tbsp→tablespoon, shows correctly after save); the summary line reads the persisted `ingredient.qty`/`unit`, not the editable local state.
- **Reviewed disclosure default:** `ReviewedSection` only mounts after the recipe loads, so `useState(defaultOpen)` captures the correct initial value (`needsReview.length === 0`).
```

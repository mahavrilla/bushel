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

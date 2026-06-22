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
  onSaved,
}: {
  recipeId: number;
  ingredient: IngredientRead;
  onSaved: (recipe: RecipeRead) => void;
}) {
  const [qty, setQty] = useState(ingredient.qty?.toString() ?? "");
  const [unit, setUnit] = useState(ingredient.unit ?? "");
  const [changing, setChanging] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <Card className={ingredient.needs_review ? "border-warning/40 bg-warning-tint" : ""}>
      {error && <ErrorBanner message={error} />}
      <div className="mb-2 flex items-center gap-2">
        <span className="font-medium text-heading">{ingredient.raw_text}</span>
        {ingredient.needs_review && <Pill tone="warning">Needs review</Pill>}
        <Button
          variant="link"
          className="ml-auto"
          aria-label={`Delete ${ingredient.raw_text}`}
          onClick={remove}
        >
          🗑
        </Button>
      </div>

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

      <div className="mt-2 flex flex-wrap items-end gap-3">
        <Input label="Amount" value={qty} onChange={(e) => setQty(e.target.value)} className="w-24" />
        <Input label="Unit" value={unit} onChange={(e) => setUnit(e.target.value)} className="w-28" />
        <Button variant="secondary" aria-label={`Save ${ingredient.raw_text}`} onClick={save}>
          Save
        </Button>
      </div>
    </Card>
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

  const flagged = recipe.ingredients.filter((i) => i.needs_review).length;

  return (
    <div>
      <PageHeader title={recipe.title} />
      <p className="mb-2 text-sm text-muted">
        Each line from your recipe is matched to a grocery ingredient. Fix the amount or the match
        if it's wrong.
      </p>
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
      <form
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
        className="mt-4 flex items-end gap-2"
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

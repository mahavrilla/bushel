import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getRecipe, updateIngredient } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
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

  async function save() {
    onSaved(
      await updateIngredient(recipeId, ingredient.id, {
        qty: qty === "" ? undefined : Number(qty),
        unit: unit === "" ? undefined : unit,
      }),
    );
  }

  async function remap(ingredientId: number) {
    onSaved(await updateIngredient(recipeId, ingredient.id, { ingredient_id: ingredientId }));
    setChanging(false);
  }

  return (
    <Card className={ingredient.needs_review ? "border-accent bg-tint-amber" : ""}>
      <div className="mb-2 flex items-center gap-2">
        <span className="font-medium text-heading">{ingredient.raw_text}</span>
        {ingredient.needs_review && <Pill tone="warning">Needs review</Pill>}
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted">Matched to:</span>
        <strong className="text-heading">{ingredient.ingredient_name ?? "—"}</strong>
        <Button variant="link" className="ml-auto" onClick={() => setChanging((c) => !c)}>
          Change
        </Button>
      </div>
      {changing && <IngredientPicker onPick={remap} />}

      <div className="mt-2 flex flex-wrap items-end gap-3">
        <Input label="Amount" value={qty} onChange={(e) => setQty(e.target.value)} className="w-24" />
        <Input label="Unit" value={unit} onChange={(e) => setUnit(e.target.value)} className="w-28" />
        <Button variant="secondary" onClick={save}>
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
    </div>
  );
}

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

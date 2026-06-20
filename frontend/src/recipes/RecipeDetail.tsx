import { useEffect, useState } from "react";

import { getRecipe, updateIngredient } from "../api";
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
    <li style={{ background: ingredient.needs_review ? "#fff3cd" : "transparent" }}>
      <span>{ingredient.raw_text}</span> → <strong>{ingredient.ingredient_name}</strong>
      <label>
        Qty for {ingredient.raw_text}
        <input value={qty} onChange={(e) => setQty(e.target.value)} />
      </label>
      <label>
        Unit for {ingredient.raw_text}
        <input value={unit} onChange={(e) => setUnit(e.target.value)} />
      </label>
      <button onClick={save}>Save {ingredient.raw_text}</button>
    </li>
  );
}

export function RecipeDetail({ recipeId }: { recipeId: number }) {
  const [recipe, setRecipe] = useState<RecipeRead | null>(null);

  useEffect(() => {
    getRecipe(recipeId).then(setRecipe).catch(() => setRecipe(null));
  }, [recipeId]);

  if (recipe === null) return <p>Loading…</p>;

  const flagged = recipe.ingredients.filter((i) => i.needs_review).length;

  return (
    <div>
      <h2>{recipe.title}</h2>
      {flagged > 0 ? (
        <p role="status">{flagged} item{flagged === 1 ? "" : "s"} need{flagged === 1 ? "s" : ""} review</p>
      ) : (
        <p role="status">All items reviewed ✓</p>
      )}
      <ul>
        {recipe.ingredients.map((ing) => (
          <Row key={ing.id} recipeId={recipe.id} ingredient={ing} onSaved={setRecipe} />
        ))}
      </ul>
    </div>
  );
}

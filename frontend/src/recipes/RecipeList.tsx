import { useEffect, useState } from "react";

import { addRecipeToList, listRecipes } from "../api";
import type { RecipeSummary } from "./types";

export function RecipeList({ onOpen }: { onOpen: (id: number) => void }) {
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
          <button onClick={() => onOpen(r.id)}>
            {r.title} ({r.servings} servings)
          </button>
          <button aria-label={`Add ${r.title} to list`} onClick={() => addRecipeToList(r.id)}>
            Add to list
          </button>
        </li>
      ))}
    </ul>
  );
}

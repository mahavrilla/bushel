import { useEffect, useState } from "react";

import { getList, removeRecipeFromList, updateListServings } from "../api";
import type { GroceryListData, ListRecipe, SubQuantity } from "./types";

function formatQuantities(quantities: SubQuantity[]): string {
  if (quantities.length === 0) return "";
  return quantities
    .map((q) => (q.qty === null ? `as needed${q.unit ? ` (${q.unit})` : ""}` : `${q.qty}${q.unit ? ` ${q.unit}` : ""}`))
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

  return (
    <li>
      <span>{recipe.title}</span>
      <input
        aria-label={`Servings for ${recipe.title}`}
        value={servings}
        onChange={(e) => setServings(e.target.value)}
      />
      <button aria-label={`Update ${recipe.title}`} onClick={async () => onChange(await updateListServings(recipe.recipe_id, Number(servings)))}>
        Update
      </button>
      <button aria-label={`Remove ${recipe.title}`} onClick={async () => onChange(await removeRecipeFromList(recipe.recipe_id))}>
        Remove
      </button>
    </li>
  );
}

export function GroceryList() {
  const [list, setList] = useState<GroceryListData | null>(null);

  useEffect(() => {
    getList().then(setList).catch(() => setList(null));
  }, []);

  if (list === null) return <p>Loading…</p>;
  if (list.recipes.length === 0) return <p>No recipes on your list yet. Add some from the Recipes tab.</p>;

  return (
    <div>
      <h2>Grocery List</h2>
      <section>
        <h3>Recipes</h3>
        <ul>
          {list.recipes.map((r) => (
            <RecipeRow key={r.recipe_id} recipe={r} onChange={setList} />
          ))}
        </ul>
      </section>
      <section>
        <h3>Shopping list</h3>
        <ul>
          {list.items.map((item) => (
            <li key={item.ingredient_id}>
              <strong>{item.ingredient_name}</strong>: {formatQuantities(item.quantities)}
              {item.category ? ` (${item.category})` : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

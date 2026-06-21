import { useEffect, useState } from "react";

import { getList, removeRecipeFromList, updateListServings } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import type { GroceryListData, ListRecipe, SubQuantity } from "./types";
import { MatchAndSend } from "./MatchAndSend";

function formatQuantities(quantities: SubQuantity[]): string {
  if (quantities.length === 0) return "";
  return quantities
    .map((q) =>
      q.qty === null ? `as needed${q.unit ? ` (${q.unit})` : ""}` : `${q.qty}${q.unit ? ` ${q.unit}` : ""}`,
    )
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

  useEffect(() => {
    setServings(recipe.servings.toString());
  }, [recipe.servings]);

  async function handleUpdate() {
    const n = Number(servings);
    if (servings.trim() === "" || !Number.isFinite(n)) return;
    onChange(await updateListServings(recipe.recipe_id, n));
  }

  return (
    <li className="flex flex-wrap items-end gap-2 rounded-xl border border-line bg-surface px-3 py-2">
      <span className="font-medium text-heading">{recipe.title}</span>
      <input
        aria-label={`Servings for ${recipe.title}`}
        value={servings}
        onChange={(e) => setServings(e.target.value)}
        className="w-20 rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary"
      />
      <Button variant="secondary" aria-label={`Update ${recipe.title}`} onClick={handleUpdate}>
        Update
      </Button>
      <Button
        variant="link"
        aria-label={`Remove ${recipe.title}`}
        onClick={async () => onChange(await removeRecipeFromList(recipe.recipe_id))}
      >
        Remove
      </Button>
    </li>
  );
}

export function GroceryList() {
  const [list, setList] = useState<GroceryListData | null>(null);

  useEffect(() => {
    getList().then(setList).catch(() => setList(null));
  }, []);

  if (list === null)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Grocery list" />

      {list.recipes.length === 0 ? (
        <EmptyState icon="🧺" message="No recipes on your list yet. Add some from the Recipes tab." />
      ) : (
        <>
          <Card className="flex flex-col gap-2">
            <h3 className="text-lg font-semibold text-heading">Recipes</h3>
            <ul className="flex flex-col gap-2">
              {list.recipes.map((r) => (
                <RecipeRow key={r.recipe_id} recipe={r} onChange={setList} />
              ))}
            </ul>
          </Card>

          <Card className="flex flex-col gap-2">
            <h3 className="text-lg font-semibold text-heading">Shopping list</h3>
            <ul className="flex flex-col gap-1">
              {list.items.map((item) => (
                <li key={item.ingredient_id} className="flex items-center gap-2 border-b border-line py-1.5 text-sm last:border-0">
                  <strong className="text-heading">{item.ingredient_name}</strong>
                  <span className="text-ink">{formatQuantities(item.quantities)}</span>
                  {item.category && <span className="ml-auto text-xs text-muted">{item.category}</span>}
                </li>
              ))}
            </ul>
          </Card>

          <MatchAndSend />
        </>
      )}
    </div>
  );
}

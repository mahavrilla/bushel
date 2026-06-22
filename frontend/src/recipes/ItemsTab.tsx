import { useEffect, useState } from "react";

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

  useEffect(() => {
    setServings(recipe.servings.toString());
  }, [recipe.servings]);

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

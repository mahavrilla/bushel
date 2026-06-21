import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { addRecipeToList, listRecipes } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import type { RecipeSummary } from "./types";

export function RecipeList() {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);

  useEffect(() => {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, []);

  const addAction = (
    <Link
      to="/recipes/new"
      className="inline-flex items-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
    >
      + Add recipe
    </Link>
  );

  return (
    <div>
      <PageHeader title="Recipes" action={addAction} />
      {recipes === null ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : recipes.length === 0 ? (
        <EmptyState icon="📖" message="No recipes yet. Add one to get started." />
      ) : (
        <ul className="flex flex-col gap-2">
          {recipes.map((r) => (
            <li key={r.id}>
              <Card className="flex items-center gap-3">
                <Link to={`/recipes/${r.id}`} className="font-medium text-heading hover:underline">
                  {r.title}
                </Link>
                <span className="text-sm text-muted">{r.servings} servings</span>
                <Button
                  variant="secondary"
                  className="ml-auto"
                  aria-label={`Add ${r.title} to list`}
                  onClick={() => addRecipeToList(r.id)}
                >
                  Add to list
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

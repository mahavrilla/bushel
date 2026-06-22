import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { addRecipeToList, deleteRecipe, listRecipes } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import type { RecipeSummary } from "./types";

export function RecipeList() {
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  function load() {
    listRecipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }

  useEffect(() => {
    load();
  }, []);

  async function remove(r: RecipeSummary) {
    if (!window.confirm(`Delete ${r.title}? This also removes it from your grocery list.`)) return;
    setError(null);
    try {
      await deleteRecipe(r.id);
      load();
    } catch {
      setError("Could not delete that recipe. Please try again.");
    }
  }

  const addAction = (
    <Link
      to="/recipes/new"
      className="inline-flex min-h-[44px] items-center rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover active:bg-primary-hover"
    >
      + Add recipe
    </Link>
  );

  const filtered =
    recipes?.filter((r) => r.title.toLowerCase().includes(query.trim().toLowerCase())) ?? [];

  return (
    <div>
      <PageHeader title="Recipes" action={addAction} />
      {error && <ErrorBanner message={error} />}
      {recipes === null ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : recipes.length === 0 ? (
        <EmptyState icon="📖" message="No recipes yet. Add one to get started." />
      ) : (
        <>
          <div className="mb-4">
            <Input
              type="search"
              label="Search recipes"
              placeholder="Search recipes…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {filtered.length === 0 ? (
            <EmptyState icon="🔍" message="No recipes match that search." />
          ) : (
            <ul className="flex flex-col gap-2">
              {filtered.map((r) => (
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
                    <Button
                      variant="link"
                      aria-label={`Delete ${r.title}`}
                      onClick={() => remove(r)}
                    >
                      🗑
                    </Button>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

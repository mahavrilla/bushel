import type { RecipeRead, RecipeSummary } from "./recipes/types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export async function importRecipe(url: string): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return json<RecipeRead>(res);
}

export async function createRecipe(
  title: string,
  servings: number,
  rawLines: string[],
): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, servings, raw_lines: rawLines }),
  });
  return json<RecipeRead>(res);
}

export async function getRecipe(id: number): Promise<RecipeRead> {
  return json<RecipeRead>(await fetch(`${BASE_URL}/recipes/${id}`));
}

export async function listRecipes(): Promise<RecipeSummary[]> {
  return json<RecipeSummary[]>(await fetch(`${BASE_URL}/recipes`));
}

export async function updateIngredient(
  recipeId: number,
  rowId: number,
  patch: { qty?: number; unit?: string; ingredient_id?: number },
): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes/${recipeId}/ingredients/${rowId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return json<RecipeRead>(res);
}

import type { ConfirmProductBody, GroceryListData, IngredientOption, KrogerLocation, KrogerStatus, MatchData, PantryView, ProductChoice, RecipeRead, RecipeSummary, SendResult, StapleView } from "./recipes/types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export class ApiError extends Error {
  status: number;
  constructor(status: number) {
    super(`Request failed: ${status}`);
    this.status = status;
  }
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new ApiError(res.status);
  return res.json() as Promise<T>;
}

export async function extractIngredients(text: string): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/recipes/extract-ingredients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const body = await json<{ lines: string[] }>(res);
  return body.lines;
}

export async function importRecipe(url: string): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return json<RecipeRead>(res);
}

export async function importPhotoRecipe(files: File[]): Promise<RecipeRead> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const res = await fetch(`${BASE_URL}/recipes/import-photo`, {
    method: "POST",
    body: form,
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

export async function addIngredient(recipeId: number, rawText: string): Promise<RecipeRead> {
  const res = await fetch(`${BASE_URL}/recipes/${recipeId}/ingredients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText }),
  });
  return json<RecipeRead>(res);
}

export async function deleteIngredient(recipeId: number, rowId: number): Promise<RecipeRead> {
  return json<RecipeRead>(
    await fetch(`${BASE_URL}/recipes/${recipeId}/ingredients/${rowId}`, { method: "DELETE" }),
  );
}

export async function deleteRecipe(id: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/recipes/${id}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status);
}

export async function searchIngredients(q: string): Promise<IngredientOption[]> {
  return json<IngredientOption[]>(
    await fetch(`${BASE_URL}/ingredients?q=${encodeURIComponent(q)}`),
  );
}

export async function createIngredient(name: string): Promise<IngredientOption> {
  const res = await fetch(`${BASE_URL}/ingredients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return json<IngredientOption>(res);
}

export async function getList(): Promise<GroceryListData> {
  return json<GroceryListData>(await fetch(`${BASE_URL}/list`, undefined));
}

export async function addRecipeToList(
  recipeId: number,
  servings?: number,
): Promise<GroceryListData> {
  const res = await fetch(`${BASE_URL}/list/recipes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recipe_id: recipeId, servings }),
  });
  return json<GroceryListData>(res);
}

export async function updateListServings(
  recipeId: number,
  servings: number,
): Promise<GroceryListData> {
  const res = await fetch(`${BASE_URL}/list/recipes/${recipeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ servings }),
  });
  return json<GroceryListData>(res);
}

export async function removeRecipeFromList(recipeId: number): Promise<GroceryListData> {
  const res = await fetch(`${BASE_URL}/list/recipes/${recipeId}`, { method: "DELETE" });
  return json<GroceryListData>(res);
}

export async function getKrogerStatus(): Promise<KrogerStatus> {
  return json<KrogerStatus>(await fetch(`${BASE_URL}/kroger/status`));
}

export async function getKrogerLoginUrl(): Promise<{ url: string }> {
  return json<{ url: string }>(await fetch(`${BASE_URL}/kroger/login`));
}

export async function searchLocations(zip: string): Promise<KrogerLocation[]> {
  return json<KrogerLocation[]>(
    await fetch(`${BASE_URL}/kroger/locations?zip=${encodeURIComponent(zip)}`),
  );
}

export async function getMatch(): Promise<MatchData> {
  return json<MatchData>(await fetch(`${BASE_URL}/list/match`));
}

export async function searchItemProducts(
  itemId: number,
  q: string,
  start = 0,
  limit = 24,
): Promise<ProductChoice[]> {
  return json<ProductChoice[]>(
    await fetch(
      `${BASE_URL}/list/items/${itemId}/products?q=${encodeURIComponent(q)}&start=${start}&limit=${limit}`,
    ),
  );
}

export async function confirmProduct(
  itemId: number,
  body: ConfirmProductBody,
): Promise<MatchData> {
  const res = await fetch(`${BASE_URL}/list/items/${itemId}/product`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<MatchData>(res);
}

export async function setStore(locationId: string, name?: string | null): Promise<MatchData> {
  const res = await fetch(`${BASE_URL}/list/store`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ location_id: locationId, name: name ?? null }),
  });
  return json<MatchData>(res);
}

export async function sendCart(modality: string): Promise<SendResult> {
  const res = await fetch(`${BASE_URL}/list/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modality }),
  });
  return json<SendResult>(res);
}

export async function setPantryDecision(itemId: number, keep: boolean): Promise<PantryView> {
  const res = await fetch(`${BASE_URL}/list/items/${itemId}/pantry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keep }),
  });
  return json<PantryView>(res);
}

export async function getStaples(): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/list/staples`));
}

export async function addStaple(name: string): Promise<StapleView> {
  const res = await fetch(`${BASE_URL}/staples`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return json<StapleView>(res);
}

export async function removeStaple(id: number): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/staples/${id}`, { method: "DELETE" }));
}

export async function setStapleAutoAdd(id: number, autoAdd: boolean): Promise<StapleView> {
  const res = await fetch(`${BASE_URL}/staples/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auto_add: autoAdd }),
  });
  return json<StapleView>(res);
}

export async function addStapleToTrip(id: number): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/list/staples/${id}`, { method: "POST" }));
}

export async function removeStapleFromTrip(id: number): Promise<StapleView> {
  return json<StapleView>(await fetch(`${BASE_URL}/list/staples/${id}`, { method: "DELETE" }));
}

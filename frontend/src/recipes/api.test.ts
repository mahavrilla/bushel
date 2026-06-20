import { afterEach, describe, expect, it, vi } from "vitest";

import { importRecipe, listRecipes, updateIngredient } from "../api";

afterEach(() => vi.restoreAllMocks());

describe("recipe api", () => {
  it("importRecipe posts the url", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 1, title: "X", servings: 2, source_url: null, ingredients: [] }), { status: 201 }),
    );
    const recipe = await importRecipe("https://example.com");
    expect(recipe.title).toBe("X");
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/recipes/import"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listRecipes fetches summaries", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "X", servings: 2 }]), { status: 200 }),
    );
    const list = await listRecipes();
    expect(list[0].title).toBe("X");
  });

  it("updateIngredient patches and returns the recipe", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 1, title: "X", servings: 2, source_url: null, ingredients: [] }), { status: 200 }),
    );
    const recipe = await updateIngredient(1, 5, { qty: 2 });
    expect(recipe.id).toBe(1);
  });

  it("throws on non-ok", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 422 }));
    await expect(importRecipe("bad")).rejects.toThrow();
  });
});

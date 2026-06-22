import { afterEach, describe, expect, it, vi } from "vitest";

import { createIngredient, deleteRecipe, importRecipe, listRecipes, searchIngredients, updateIngredient } from "../api";

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

  it("deleteRecipe issues a DELETE", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await deleteRecipe(7);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/recipes/7"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("deleteRecipe throws on non-ok", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 404 }));
    await expect(deleteRecipe(7)).rejects.toThrow();
  });

  it("searchIngredients fetches options for a query", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 3, canonical_name: "garlic" }]), { status: 200 }),
    );
    const results = await searchIngredients("gar");
    expect(results[0].canonical_name).toBe("garlic");
    expect(spy).toHaveBeenCalledWith(expect.stringContaining("/ingredients?q=gar"));
  });

  it("createIngredient posts the name", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 9, canonical_name: "fresh basil" }), { status: 201 }),
    );
    const opt = await createIngredient("Fresh Basil");
    expect(opt.id).toBe(9);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/ingredients"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

import { addRecipeToList, getList, removeRecipeFromList, updateListServings } from "../api";

afterEach(() => vi.restoreAllMocks());

const listJson = { id: 1, status: "draft", recipes: [], items: [] };

describe("list api", () => {
  it("getList GETs /list", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    const list = await getList();
    expect(list.status).toBe("draft");
    expect(spy).toHaveBeenCalledWith(expect.stringContaining("/list"), undefined);
  });

  it("addRecipeToList POSTs recipe_id and servings", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    await addRecipeToList(5, 4);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/list/recipes"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("updateListServings PATCHes", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    await updateListServings(5, 6);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/list/recipes/5"),
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("removeRecipeFromList DELETEs", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listJson), { status: 200 }),
    );
    await removeRecipeFromList(5);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/list/recipes/5"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

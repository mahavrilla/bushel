import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GroceryList } from "./GroceryList";

afterEach(() => vi.restoreAllMocks());

const emptyList = { id: 1, status: "draft", recipes: [], items: [] };

const populatedList = {
  id: 1,
  status: "draft",
  recipes: [{ recipe_id: 5, title: "Pancakes", servings: 6, default_servings: 4 }],
  items: [
    {
      ingredient_id: 10, ingredient_name: "garlic", category: "produce",
      quantities: [{ qty: 3, unit: "clove" }, { qty: 1, unit: "tbsp" }],
      source_recipe_ids: [5], pantry_status: "needed",
    },
    {
      ingredient_id: 11, ingredient_name: "flour", category: "baking",
      quantities: [{ qty: 4, unit: "cup" }], source_recipe_ids: [5], pantry_status: "needed",
    },
  ],
};

describe("GroceryList", () => {
  it("shows an empty state when no recipes", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(emptyList), { status: 200 }),
    );
    render(<GroceryList />);
    expect(await screen.findByText(/no recipes on your list/i)).toBeInTheDocument();
  });

  it("renders member recipes and consolidated items with multi-unit quantities", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(populatedList), { status: 200 }),
    );
    render(<GroceryList />);
    expect(await screen.findByText(/pancakes/i)).toBeInTheDocument();
    expect(await screen.findByText(/3 clove \+ 1 tbsp/i)).toBeInTheDocument();
    expect(await screen.findByText(/4 cup/i)).toBeInTheDocument();
  });

  it("editing servings calls PATCH and refreshes", async () => {
    const refreshed = {
      ...populatedList,
      recipes: [{ ...populatedList.recipes[0], servings: 8 }],
    };
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(populatedList), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(refreshed), { status: 200 }));

    render(<GroceryList />);
    const input = await screen.findByLabelText(/servings for pancakes/i);
    await userEvent.clear(input);
    await userEvent.type(input, "8");
    await userEvent.click(screen.getByRole("button", { name: /update pancakes/i }));

    await waitFor(() =>
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining("/list/recipes/5"),
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ItemsTab } from "./ItemsTab";
import type { GroceryListData } from "./types";

afterEach(() => vi.restoreAllMocks());

const list: GroceryListData = {
  id: 1,
  status: "draft",
  recipes: [
    { recipe_id: 9, title: "Pancakes", servings: 4, default_servings: 2 },
    { recipe_id: 10, title: "Soup", servings: 2, default_servings: 2 },
    { recipe_id: 11, title: "Stew", servings: 2, default_servings: 2 },
  ],
  items: [
    { item_id: 100, ingredient_id: 5, ingredient_name: "flour", category: "baking", quantities: [{ qty: 3, unit: "cup" }], source_recipe_ids: [9, 10], pantry_status: "needed" },
    { item_id: 102, ingredient_id: 7, ingredient_name: "broth", category: "pantry", quantities: [{ qty: 2, unit: "cup" }], source_recipe_ids: [9, 10, 11], pantry_status: "needed" },
    { item_id: 101, ingredient_id: 6, ingredient_name: "garlic", category: "produce", quantities: [{ qty: 2, unit: "clove" }], source_recipe_ids: [10], pantry_status: "skipped" },
  ],
};

describe("ItemsTab", () => {
  it("shows items with consolidated amount and recipe sources", async () => {
    render(<ItemsTab list={list} reload={vi.fn()} />);
    expect(screen.getByText("flour")).toBeInTheDocument();
    expect(screen.getByText(/3 cup/)).toBeInTheDocument();
    expect(screen.getByText(/from Pancakes \+ Soup/i)).toBeInTheDocument();
    expect(screen.getByText(/from 3 recipes/i)).toBeInTheDocument();
  });

  it("marks an item already-have via setPantryDecision and reloads", async () => {
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    const reload = vi.fn();
    render(<ItemsTab list={list} reload={reload} />);
    await userEvent.click(screen.getByRole("button", { name: /already have flour/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(100, false));
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  it("can undo a skipped item", async () => {
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    render(<ItemsTab list={list} reload={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /undo garlic/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(101, true));
  });
});

import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { GroceryList } from "./GroceryList";

beforeEach(() => {
  vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
});
afterEach(() => vi.restoreAllMocks());

const list = {
  id: 1,
  status: "draft",
  recipes: [{ recipe_id: 9, title: "Pancakes", servings: 4, default_servings: 2 }],
  items: [
    { ingredient_id: 5, ingredient_name: "flour", category: "baking", quantities: [{ qty: 3, unit: "cup" }], source_recipe_ids: [9], pantry_status: "needed" },
  ],
};

describe("GroceryList", () => {
  it("renders recipes and shopping items", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    expect(await screen.findByText(/pancakes/i)).toBeInTheDocument();
    expect(await screen.findByText(/flour/i)).toBeInTheDocument();
  });

  it("shows an empty state when no recipes are on the list", async () => {
    vi.spyOn(api, "getList").mockResolvedValue({ id: 1, status: "draft", recipes: [], items: [] });
    render(<GroceryList />);
    expect(await screen.findByText(/no recipes on your list/i)).toBeInTheDocument();
  });

  it("includes the Review & send panel", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    expect(await screen.findByText(/review & send/i)).toBeInTheDocument();
  });
});

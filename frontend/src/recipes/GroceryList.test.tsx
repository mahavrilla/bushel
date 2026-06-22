import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { GroceryList } from "./GroceryList";

beforeEach(() => {
  vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
  vi.spyOn(api, "getStaples").mockResolvedValue({ staples: [] });
});
afterEach(() => vi.restoreAllMocks());

const list = {
  id: 1,
  status: "draft",
  recipes: [{ recipe_id: 9, title: "Pancakes", servings: 4, default_servings: 2 }],
  items: [
    { item_id: 100, ingredient_id: 5, ingredient_name: "flour", category: "baking", quantities: [{ qty: 3, unit: "cup" }], source_recipe_ids: [9], pantry_status: "needed" },
  ],
};

describe("GroceryList", () => {
  it("shows the Items tab with consolidated items by default", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    expect(await screen.findByText("flour")).toBeInTheDocument();
  });

  it("empty state when no recipes", async () => {
    vi.spyOn(api, "getList").mockResolvedValue({ id: 1, status: "draft", recipes: [], items: [] });
    render(<GroceryList />);
    expect(await screen.findByText(/no recipes on your list/i)).toBeInTheDocument();
  });

  it("switches to the Cart tab", async () => {
    vi.spyOn(api, "getList").mockResolvedValue(list);
    render(<GroceryList />);
    await screen.findByText("flour");
    await userEvent.click(screen.getByRole("tab", { name: /cart/i }));
    await waitFor(() => expect(api.getMatch).toHaveBeenCalled());
  });
});

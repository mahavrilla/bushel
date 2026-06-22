import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { renderWithRouter } from "../test/renderWithRouter";
import { RecipeDetail } from "./RecipeDetail";

afterEach(() => vi.restoreAllMocks());

const recipe = {
  id: 1,
  title: "Pancakes",
  servings: 4,
  source_url: null,
  ingredients: [
    { id: 10, raw_text: "2 cups flour", qty: 2, unit: "cup", ingredient_id: 5, ingredient_name: "flour", parse_source: "library", needs_review: false },
  ],
};

function show() {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify(recipe), { status: 200 }));
  renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
}

describe("RecipeDetail", () => {
  it("renders the recipe title", async () => {
    show();
    expect(await screen.findByRole("heading", { name: /pancakes/i })).toBeInTheDocument();
  });

  it("shows the reviewed status", async () => {
    show();
    expect(await screen.findByText(/all items reviewed/i)).toBeInTheDocument();
  });

  it("shows the count of items needing review", async () => {
    vi.spyOn(api, "getRecipe").mockResolvedValue({
      ...recipe,
      ingredients: [{ ...recipe.ingredients[0], needs_review: true }],
    });
    renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
    expect(await screen.findByText(/1 item needs review/i)).toBeInTheDocument();
  });

  it("saves an edited ingredient via updateIngredient", async () => {
    vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
    const update = vi.spyOn(api, "updateIngredient").mockResolvedValue(recipe);
    renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
    await userEvent.click(await screen.findByRole("button", { name: /save/i }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, 10, { qty: 2, unit: "cup" }));
  });

  it("shows the intro and labelled fields", async () => {
    vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
    renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
    expect(await screen.findByText("Matched to:")).toBeInTheDocument();
    expect(screen.getByText(/each line from your recipe/i)).toBeInTheDocument();
  });

  it("re-maps the ingredient via the picker", async () => {
    vi.spyOn(api, "getRecipe").mockResolvedValue(recipe);
    vi.spyOn(api, "searchIngredients").mockResolvedValue([{ id: 8, canonical_name: "garlic powder" }]);
    const update = vi.spyOn(api, "updateIngredient").mockResolvedValue(recipe);
    renderWithRouter(<RecipeDetail />, { path: "/recipes/:id", initialEntries: ["/recipes/1"] });
    await userEvent.click(await screen.findByRole("button", { name: /change/i }));
    await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "gar");
    await userEvent.click(await screen.findByRole("button", { name: "garlic powder" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, 10, { ingredient_id: 8 }));
  });
});

import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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
});

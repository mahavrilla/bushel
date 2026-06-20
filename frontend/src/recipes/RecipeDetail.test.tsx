import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecipeDetail } from "./RecipeDetail";

afterEach(() => vi.restoreAllMocks());

const flaggedRecipe = {
  id: 1,
  title: "Pancakes",
  servings: 4,
  source_url: null,
  ingredients: [
    {
      id: 10, raw_text: "a pinch of saffron", qty: null, unit: null,
      ingredient_id: 5, ingredient_name: "saffron", parse_source: "library_low_confidence",
      needs_review: true,
    },
    {
      id: 11, raw_text: "1 egg", qty: 1, unit: null, ingredient_id: 6,
      ingredient_name: "egg", parse_source: "library", needs_review: false,
    },
  ],
};

describe("RecipeDetail", () => {
  it("shows the review banner with the flagged count", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(flaggedRecipe), { status: 200 }),
    );
    render(<RecipeDetail recipeId={1} />);
    expect(await screen.findByText(/1 item needs review/i)).toBeInTheDocument();
  });

  it("saving an edited qty calls PATCH and refreshes", async () => {
    const cleared = {
      ...flaggedRecipe,
      ingredients: [
        { ...flaggedRecipe.ingredients[0], qty: 1, needs_review: false },
        flaggedRecipe.ingredients[1],
      ],
    };
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(flaggedRecipe), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(cleared), { status: 200 }));

    render(<RecipeDetail recipeId={1} />);
    const qtyInput = await screen.findByLabelText(/qty for a pinch of saffron/i);
    await userEvent.clear(qtyInput);
    await userEvent.type(qtyInput, "1");
    await userEvent.click(screen.getByRole("button", { name: /save a pinch of saffron/i }));

    await waitFor(() =>
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining("/recipes/1/ingredients/10"),
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
    expect(await screen.findByText(/all items reviewed/i)).toBeInTheDocument();
  });
});

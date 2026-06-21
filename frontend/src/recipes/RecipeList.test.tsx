import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithRouter } from "../test/renderWithRouter";
import { RecipeList } from "./RecipeList";

afterEach(() => vi.restoreAllMocks());

describe("RecipeList", () => {
  it("links each recipe to its detail route", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    );
    renderWithRouter(<RecipeList />);
    const link = await screen.findByRole("link", { name: /pancakes/i });
    expect(link).toHaveAttribute("href", "/recipes/1");
  });

  it("shows an empty state when there are no recipes", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
    renderWithRouter(<RecipeList />);
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });

  it("adds a recipe to the list", async () => {
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 1, status: "draft", recipes: [], items: [] }), { status: 200 }),
      );
    renderWithRouter(<RecipeList />);
    await userEvent.click(await screen.findByRole("button", { name: /add pancakes to list/i }));
    await waitFor(() =>
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining("/list/recipes"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
});

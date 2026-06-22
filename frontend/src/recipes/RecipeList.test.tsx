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

  it("offers an Add recipe action in the header", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
    renderWithRouter(<RecipeList />);
    const add = await screen.findByRole("link", { name: /add recipe/i });
    expect(add).toHaveAttribute("href", "/recipes/new");
  });

  it("filters recipes by the search query", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify([
          { id: 1, title: "Pancakes", servings: 4 },
          { id: 2, title: "Omelette", servings: 2 },
        ]),
        { status: 200 },
      ),
    );
    renderWithRouter(<RecipeList />);
    await screen.findByRole("link", { name: /pancakes/i });
    await userEvent.type(screen.getByRole("searchbox", { name: /search recipes/i }), "ome");
    expect(screen.queryByRole("link", { name: /pancakes/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /omelette/i })).toBeInTheDocument();
  });

  it("shows a no-match message when search matches nothing", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    );
    renderWithRouter(<RecipeList />);
    await screen.findByRole("link", { name: /pancakes/i });
    await userEvent.type(screen.getByRole("searchbox", { name: /search recipes/i }), "zzz");
    expect(screen.getByText(/no recipes match/i)).toBeInTheDocument();
  });

  it("deletes a recipe after confirmation and refreshes", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    renderWithRouter(<RecipeList />);
    await userEvent.click(await screen.findByRole("button", { name: /delete pancakes/i }));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.stringContaining("/recipes/1"),
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });

  it("does not delete when confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
      );
    renderWithRouter(<RecipeList />);
    await userEvent.click(await screen.findByRole("button", { name: /delete pancakes/i }));
    expect(spy).toHaveBeenCalledTimes(1); // only the initial list fetch
  });
});

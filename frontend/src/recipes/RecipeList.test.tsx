import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecipeList } from "./RecipeList";

afterEach(() => vi.restoreAllMocks());

describe("RecipeList", () => {
  it("renders recipe titles from the API", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: 1, title: "Pancakes", servings: 4 }]), { status: 200 }),
    );
    render(<RecipeList onOpen={() => {}} />);
    expect(await screen.findByText(/pancakes/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no recipes", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
    render(<RecipeList onOpen={() => {}} />);
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddRecipe } from "./AddRecipe";

afterEach(() => vi.restoreAllMocks());

const recipeJson = { id: 7, title: "X", servings: 2, source_url: null, ingredients: [] };

describe("AddRecipe", () => {
  it("imports by URL and calls onCreated with the new id", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(recipeJson), { status: 201 }),
    );
    const onCreated = vi.fn();
    render(<AddRecipe onCreated={onCreated} />);

    await userEvent.type(screen.getByLabelText(/recipe url/i), "https://example.com/x");
    await userEvent.click(screen.getByRole("button", { name: /import/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(7));
  });

  it("shows an error when import fails", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("bad", { status: 422 }));
    render(<AddRecipe onCreated={() => {}} />);

    await userEvent.type(screen.getByLabelText(/recipe url/i), "https://bad");
    await userEvent.click(screen.getByRole("button", { name: /import/i }));

    expect(await screen.findByText(/couldn't import/i)).toBeInTheDocument();
  });
});

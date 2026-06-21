import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AddRecipe } from "./AddRecipe";

afterEach(() => vi.restoreAllMocks());

function renderAddRecipe() {
  return render(
    <MemoryRouter initialEntries={["/recipes/new"]}>
      <Routes>
        <Route path="/recipes/new" element={<AddRecipe />} />
        <Route path="/recipes/:id" element={<div>detail screen</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AddRecipe", () => {
  it("navigates to the new recipe after manual create", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 7, title: "X", servings: 1, source_url: null, ingredients: [] }), { status: 200 }),
    );
    renderAddRecipe();
    await userEvent.type(screen.getByLabelText(/title/i), "Bread");
    await userEvent.type(screen.getByLabelText(/ingredients/i), "2 cups flour");
    await userEvent.click(screen.getByRole("button", { name: /save recipe/i }));
    expect(await screen.findByText(/detail screen/i)).toBeInTheDocument();
  });

  it("shows an error when import fails", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 500 }));
    renderAddRecipe();
    await userEvent.type(screen.getByLabelText(/recipe url/i), "http://x");
    await userEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

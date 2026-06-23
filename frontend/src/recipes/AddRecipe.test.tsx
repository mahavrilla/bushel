import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import * as api from "../api";
import { AddRecipe } from "./AddRecipe";

afterEach(() => vi.restoreAllMocks());

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:mock"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});

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
    await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
    await userEvent.type(screen.getByLabelText(/title/i), "Bread");
    await userEvent.type(screen.getByLabelText(/ingredients/i), "2 cups flour");
    await userEvent.click(screen.getByRole("button", { name: /save recipe/i }));
    expect(await screen.findByText(/detail screen/i)).toBeInTheDocument();
  });

  it("navigates to the new recipe after a successful URL import", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 12, title: "Imported", servings: 2, source_url: "http://x", ingredients: [] }), { status: 200 }),
    );
    renderAddRecipe();
    await userEvent.type(screen.getByLabelText(/recipe url/i), "http://x");
    await userEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(await screen.findByText(/detail screen/i)).toBeInTheDocument();
  });

  it("shows an error when import fails", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 500 }));
    renderAddRecipe();
    await userEvent.type(screen.getByLabelText(/recipe url/i), "http://x");
    await userEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("extracts ingredients into the textarea", async () => {
    const spy = vi.spyOn(api, "extractIngredients").mockResolvedValue(["ground turkey", "olive oil"]);
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
    const textarea = screen.getByLabelText(/ingredients/i);
    await userEvent.type(textarea, "messy recipe block");
    await userEvent.click(screen.getByRole("button", { name: /extract ingredients/i }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith("messy recipe block"));
    expect(textarea).toHaveValue("ground turkey\nolive oil");
  });

  it("shows an error when extraction fails", async () => {
    vi.spyOn(api, "extractIngredients").mockRejectedValue(new Error("boom"));
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
    await userEvent.type(screen.getByLabelText(/ingredients/i), "block");
    await userEvent.click(screen.getByRole("button", { name: /extract ingredients/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("defaults to URL mode and toggles to manual", async () => {
    renderAddRecipe();
    expect(screen.getByLabelText(/recipe url/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^title$/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /manual/i }));
    expect(screen.getByLabelText(/^title$/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/recipe url/i)).not.toBeInTheDocument();
  });

  it("shows photo mode without the url or title fields", async () => {
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /photo/i }));
    expect(screen.getByLabelText(/add recipe photos/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/recipe url/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^title$/i)).not.toBeInTheDocument();
  });

  it("creates a recipe from photos and navigates to it", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ id: 21, title: "Card", servings: 2, source_url: null, ingredients: [] }),
        { status: 201 },
      ),
    );
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /photo/i }));
    const file = new File(["bytes"], "card.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText(/add recipe photos/i), file);
    await userEvent.click(screen.getByRole("button", { name: /create from photos/i }));
    expect(await screen.findByText(/detail screen/i)).toBeInTheDocument();
  });

  it("shows an error when photo import fails", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("nope", { status: 422 }));
    renderAddRecipe();
    await userEvent.click(screen.getByRole("tab", { name: /photo/i }));
    const file = new File(["bytes"], "card.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText(/add recipe photos/i), file);
    await userEvent.click(screen.getByRole("button", { name: /create from photos/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

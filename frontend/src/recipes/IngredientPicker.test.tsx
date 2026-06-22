import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IngredientPicker } from "./IngredientPicker";

afterEach(() => vi.restoreAllMocks());

describe("IngredientPicker", () => {
  it("searches and selects an existing ingredient", async () => {
    vi.spyOn(global, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify([{ id: 3, canonical_name: "garlic" }]), { status: 200 }),
      ),
    );
    const onPick = vi.fn();
    render(<IngredientPicker onPick={onPick} />);
    await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "gar");
    await userEvent.click(await screen.findByRole("button", { name: "garlic" }));
    expect(onPick).toHaveBeenCalledWith(3);
  });

  it("creates a new ingredient when none fit", async () => {
    // The picker searches on every keystroke, so use a persistent, method-aware mock:
    // GET (search) always returns no matches; POST (create) returns the new ingredient.
    const spy = vi.spyOn(global, "fetch").mockImplementation((_url, init) =>
      Promise.resolve(
        init?.method === "POST"
          ? new Response(JSON.stringify({ id: 9, canonical_name: "fresh basil" }), { status: 201 })
          : new Response("[]", { status: 200 }),
      ),
    );
    const onPick = vi.fn();
    render(<IngredientPicker onPick={onPick} />);
    await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "Fresh Basil");
    await userEvent.click(await screen.findByRole("button", { name: /create "fresh basil"/i }));
    await waitFor(() => expect(onPick).toHaveBeenCalledWith(9));
    expect(spy).toHaveBeenLastCalledWith(
      expect.stringContaining("/ingredients"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows an error when creating fails", async () => {
    vi.spyOn(global, "fetch").mockImplementation((_url, init) =>
      Promise.resolve(
        init?.method === "POST"
          ? new Response("nope", { status: 422 })
          : new Response("[]", { status: 200 }),
      ),
    );
    const onPick = vi.fn();
    render(<IngredientPicker onPick={onPick} />);
    await userEvent.type(screen.getByRole("searchbox", { name: /find ingredient/i }), "Fresh Basil");
    await userEvent.click(await screen.findByRole("button", { name: /create "fresh basil"/i }));
    expect(await screen.findByText(/couldn't create ingredient/i)).toBeInTheDocument();
    expect(onPick).not.toHaveBeenCalled();
  });
});

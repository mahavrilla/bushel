import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { PantryCheck } from "./PantryCheck";

afterEach(() => vi.restoreAllMocks());

const flagged = {
  items: [
    {
      item_id: 1, ingredient_id: 2, ingredient_name: "rice", pantry_status: "maybe_have",
      last_qty: 5, last_unit: "lb", purchased_at: "2026-06-15T00:00:00Z", days_ago: 6,
    },
  ],
};

describe("PantryCheck", () => {
  it("shows a still-have-it prompt for flagged items", async () => {
    vi.spyOn(api, "getPantry").mockResolvedValue(flagged);
    render(<PantryCheck />);
    expect(await screen.findByText(/still have it/i)).toBeInTheDocument();
    expect(screen.getByText(/rice/)).toBeInTheDocument();
  });

  it("skips an item via 'I have it'", async () => {
    vi.spyOn(api, "getPantry").mockResolvedValue(flagged);
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    render(<PantryCheck />);
    fireEvent.click(await screen.findByRole("button", { name: /i have it/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(1, false));
  });

  it("renders nothing when no items are flagged", async () => {
    vi.spyOn(api, "getPantry").mockResolvedValue({
      items: [{ item_id: 1, ingredient_id: 2, ingredient_name: "rice", pantry_status: "needed",
                last_qty: null, last_unit: null, purchased_at: null, days_ago: null }],
    });
    const { container } = render(<PantryCheck />);
    await waitFor(() => expect(api.getPantry).toHaveBeenCalled());
    expect(screen.queryByText(/still have it/i)).not.toBeInTheDocument();
    expect(container.querySelector("[data-testid='pantry-empty']")).toBeInTheDocument();
  });
});

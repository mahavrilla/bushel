import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { MatchReview } from "./MatchReview";

const baseMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    {
      item_id: 1,
      ingredient_id: 2,
      ingredient_name: "flour",
      total_qty: 3,
      total_unit: "lb",
      purchase_qty: 1,
      purchase_qty_estimated: true,
      kroger_upc: null,
      current: null,
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

describe("MatchReview", () => {
  it("lists items and flags estimated quantities", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    render(<MatchReview />);
    expect(await screen.findByText(/flour/)).toBeInTheDocument();
    expect(screen.getByText(/check quantity/i)).toBeInTheDocument();
  });

  it("searches products for an item", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const search = vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" },
    ]);
    render(<MatchReview />);
    fireEvent.click(await screen.findByRole("button", { name: /find product/i }));
    await waitFor(() => expect(search).toHaveBeenCalledWith(1, "flour"));
    expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
  });

  it("sends the cart and shows the result", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const send = vi.spyOn(api, "sendCart").mockResolvedValue({
      status: "sent_to_kroger",
      results: [{ upc: "0001", ok: true, error: null }],
    });
    render(<MatchReview />);
    fireEvent.click(await screen.findByRole("button", { name: /send to kroger cart/i }));
    await waitFor(() => expect(send).toHaveBeenCalledWith("PICKUP"));
    expect(await screen.findByText(/sent_to_kroger/)).toBeInTheDocument();
  });
});

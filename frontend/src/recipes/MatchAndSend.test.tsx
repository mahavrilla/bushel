import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ApiError } from "../api";
import { MatchAndSend } from "./MatchAndSend";

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

describe("MatchAndSend", () => {
  it("lists items and flags estimated quantities", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    render(<MatchAndSend />);
    expect(await screen.findByText(/flour/)).toBeInTheDocument();
    expect(screen.getByText(/check quantity/i)).toBeInTheDocument();
  });

  it("searches products for an item", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const search = vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" },
    ]);
    render(<MatchAndSend />);
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
    render(<MatchAndSend />);
    fireEvent.click(await screen.findByRole("button", { name: /send to kroger cart/i }));
    await waitFor(() => expect(send).toHaveBeenCalledWith("PICKUP"));
    expect(await screen.findByText(/sent_to_kroger/)).toBeInTheDocument();
  });

  it("prompts to reconnect when send returns reauth_required (409)", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    vi.spyOn(api, "sendCart").mockRejectedValue(new ApiError(409));
    render(<MatchAndSend />);
    fireEvent.click(await screen.findByRole("button", { name: /send to kroger cart/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reconnect/i);
  });

  it("shows the matched product and a Change action when already resolved", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue({
      connected: true,
      store_location_id: "L1",
      items: [
        {
          item_id: 1, ingredient_id: 2, ingredient_name: "flour",
          total_qty: 3, total_unit: "lb", purchase_qty: 3, purchase_qty_estimated: false,
          kroger_upc: "0001",
          current: { upc: "0001", description: "AP Flour", size: "5 lb", price: null, stock_level: null },
        },
      ],
    });
    render(<MatchAndSend />);
    expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /change/i })).toBeInTheDocument();
  });
});

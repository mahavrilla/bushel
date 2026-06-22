import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ApiError } from "../api";
import { CartTab } from "./CartTab";

afterEach(() => vi.restoreAllMocks());

const baseMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    { item_id: 1, ingredient_id: 2, ingredient_name: "flour", total_qty: 3, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: "0001", current: { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" } },
    { item_id: 2, ingredient_id: 3, ingredient_name: "milk", total_qty: 1, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: null, current: null },
  ],
};

describe("CartTab", () => {
  it("splits confirmed and needs-a-product", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    render(<CartTab />);
    expect(await screen.findByText(/AP Flour/)).toBeInTheDocument();
    expect(screen.getByText(/confirmed/i)).toBeInTheDocument();
    expect(screen.getByText(/needs a product/i)).toBeInTheDocument();
  });

  it("removes an item via setPantryDecision and refetches", async () => {
    const getMatch = vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const decide = vi.spyOn(api, "setPantryDecision").mockResolvedValue({ items: [] });
    render(<CartTab />);
    await screen.findByText(/AP Flour/);
    await userEvent.click(screen.getByRole("button", { name: /remove flour/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(1, false));
    await waitFor(() => expect(getMatch).toHaveBeenCalledTimes(2));
  });

  it("sends the cart", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    const send = vi.spyOn(api, "sendCart").mockResolvedValue({ status: "sent_to_kroger", results: [{ upc: "0001", ok: true, error: null }] });
    render(<CartTab />);
    await screen.findByText(/AP Flour/);
    await userEvent.click(screen.getByRole("button", { name: /send to cart/i }));
    await waitFor(() => expect(send).toHaveBeenCalledWith("PICKUP"));
  });

  it("prompts reconnect on 409", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(baseMatch);
    vi.spyOn(api, "sendCart").mockRejectedValue(new ApiError(409));
    render(<CartTab />);
    await screen.findByText(/AP Flour/);
    await userEvent.click(screen.getByRole("button", { name: /send to cart/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reconnect/i);
  });
});

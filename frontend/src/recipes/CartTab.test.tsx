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
    { item_id: 1, ingredient_id: 2, ingredient_name: "flour", total_qty: 3, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: "0001", current: { upc: "0001", description: "AP Flour", size: "5 lb", price: 3.49, stock_level: "HIGH" }, alternatives: [], insight: null },
    { item_id: 2, ingredient_id: 3, ingredient_name: "milk", total_qty: 1, total_unit: "cup", purchase_qty: 1, purchase_qty_estimated: false, kroger_upc: null, current: null, alternatives: [], insight: null },
  ],
};

const multiMatch = {
  connected: true,
  store_location_id: "L1",
  items: [
    {
      item_id: 5, ingredient_id: 9, ingredient_name: "creamer",
      total_qty: 1, total_unit: "bottle", purchase_qty: 1, purchase_qty_estimated: false,
      kroger_upc: "REG",
      current: { upc: "REG", description: "Califia Regular", size: "32 fl oz", price: 5.49, stock_level: "HIGH" },
      alternatives: [
        { upc: "REG", description: "Califia Regular", size: "32 fl oz", regular: 5.49, promo: null, effective: 5.49, unit_price: 0.17, unit_label: "fl oz", on_sale: false, stock_level: "HIGH", is_current: true, price_as_of: "2026-06-27T10:00:00Z" },
        { upc: "ORG", description: "Califia Organic", size: "25 fl oz", regular: 5.99, promo: 4.29, effective: 4.29, unit_price: 0.17, unit_label: "fl oz", on_sale: true, stock_level: "HIGH", is_current: false, price_as_of: "2026-06-27T10:00:00Z" },
      ],
      insight: { cheaper_delta_cents: 120, on_sale: true, default_out_of_stock: false },
    },
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

  it("shows a cheaper-alt badge for a multi-UPC item", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(multiMatch);
    render(<CartTab />);
    expect(await screen.findByText(/\$1\.20 cheaper/i)).toBeInTheDocument();
    expect(screen.getByText(/on sale/i)).toBeInTheDocument();
  });

  it("expands the comparison and switches the pick", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue(multiMatch);
    const sw = vi.spyOn(api, "switchPick").mockResolvedValue(multiMatch);
    render(<CartTab />);
    await screen.findByText(/\$1\.20 cheaper/i);
    await userEvent.click(screen.getByRole("button", { name: /compare/i }));
    expect(await screen.findByText(/Califia Organic/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /use this/i }));
    await waitFor(() => expect(sw).toHaveBeenCalledWith(5, "ORG"));
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { KrogerSetup } from "./KrogerSetup";

beforeEach(() => {
  // Default: no store chosen yet. Individual tests override as needed.
  vi.spyOn(api, "getMatch").mockResolvedValue({
    connected: false,
    store_location_id: null,
    items: [],
  });
});
afterEach(() => vi.restoreAllMocks());

describe("KrogerSetup", () => {
  it("shows disconnected state and a connect button", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: false, expired: false });
    render(<KrogerSetup />);
    expect(await screen.findByRole("button", { name: /connect kroger/i })).toBeInTheDocument();
  });

  it("searches stores by zip and lists them", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: false });
    const search = vi.spyOn(api, "searchLocations").mockResolvedValue([
      { location_id: "L1", name: "Kroger Downtown", address: "1 Main St" },
    ]);
    render(<KrogerSetup />);
    fireEvent.change(await screen.findByLabelText(/zip/i), { target: { value: "45202" } });
    fireEvent.click(screen.getByRole("button", { name: /find stores/i }));
    await waitFor(() => expect(search).toHaveBeenCalledWith("45202"));
    expect(await screen.findByText(/Kroger Downtown/)).toBeInTheDocument();
  });

  it("selects a store and shows it", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: false });
    vi.spyOn(api, "searchLocations").mockResolvedValue([
      { location_id: "L1", name: "Kroger Downtown", address: "1 Main St" },
    ]);
    const set = vi.spyOn(api, "setStore").mockResolvedValue({
      connected: true, store_location_id: "L1", items: [],
    });
    render(<KrogerSetup />);
    fireEvent.change(await screen.findByLabelText(/zip/i), { target: { value: "45202" } });
    fireEvent.click(screen.getByRole("button", { name: /find stores/i }));
    fireEvent.click(await screen.findByRole("button", { name: /use this store/i }));
    await waitFor(() => expect(set).toHaveBeenCalledWith("L1"));
    expect(await screen.findByText(/Selected store: L1/)).toBeInTheDocument();
  });

  it("hydrates the already-selected store on mount", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: true, expired: false });
    vi.spyOn(api, "getMatch").mockResolvedValue({
      connected: true,
      store_location_id: "L7",
      items: [],
    });
    render(<KrogerSetup />);
    expect(await screen.findByText(/Selected store: L7/)).toBeInTheDocument();
  });
});

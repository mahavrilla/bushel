import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { KrogerSetup } from "./KrogerSetup";

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
});

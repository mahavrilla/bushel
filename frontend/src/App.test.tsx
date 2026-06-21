import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";
import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
      }
      return Promise.resolve(new Response("[]", { status: 200 }));
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders the Bushel title and the recipe library by default", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: /bushel/i })).toBeInTheDocument();
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });

  it("has a way to navigate to add-recipe", async () => {
    render(<App />);
    expect(await screen.findByRole("button", { name: /add recipe/i })).toBeInTheDocument();
  });

  it("has a Grocery List nav entry", async () => {
    render(<App />);
    expect(await screen.findByRole("button", { name: /grocery list/i })).toBeInTheDocument();
  });

  it("navigates to the Kroger setup screen", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: false, expired: false });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /^kroger$/i }));
    expect(await screen.findByRole("heading", { name: /^kroger$/i })).toBeInTheDocument();
  });

  it("navigates to the Match & send screen", async () => {
    vi.spyOn(api, "getMatch").mockResolvedValue({
      connected: false,
      store_location_id: null,
      items: [],
    });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /match & send/i }));
    expect(await screen.findByRole("heading", { name: /match & send/i })).toBeInTheDocument();
  });
});

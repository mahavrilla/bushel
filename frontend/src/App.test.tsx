import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import * as api from "./api";
import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
  });
  afterEach(() => vi.restoreAllMocks());

  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>,
    );
  }

  it("renders the Bushel brand and recipes at /", async () => {
    renderAt("/");
    expect(await screen.findByText(/bushel/i)).toBeInTheDocument();
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
  });

  it("renders the grocery list route", async () => {
    vi.spyOn(api, "getList").mockResolvedValue({ id: 1, status: "draft", recipes: [], items: [] });
    vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
    renderAt("/list");
    expect(await screen.findByRole("heading", { name: /grocery list/i })).toBeInTheDocument();
  });

  it("renders the Kroger route", async () => {
    vi.spyOn(api, "getKrogerStatus").mockResolvedValue({ connected: false, expired: false });
    vi.spyOn(api, "getMatch").mockResolvedValue({ connected: false, store_location_id: null, items: [] });
    renderAt("/kroger");
    expect(await screen.findByRole("heading", { name: /^kroger$/i })).toBeInTheDocument();
  });
});

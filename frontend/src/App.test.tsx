import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the Bushel title", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: /bushel/i })).toBeInTheDocument();
  });

  it("shows backend status once health resolves", async () => {
    render(<App />);
    expect(await screen.findByText(/backend: ok/i)).toBeInTheDocument();
  });
});

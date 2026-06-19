import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the Bushel title", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /bushel/i })).toBeInTheDocument();
  });

  it("shows backend status once health resolves", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    render(<App />);
    expect(await screen.findByText(/backend: ok/i)).toBeInTheDocument();
  });
});

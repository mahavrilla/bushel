import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
});

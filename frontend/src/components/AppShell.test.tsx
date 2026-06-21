import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithRouter } from "../test/renderWithRouter";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("renders the three nav destinations as links", () => {
    renderWithRouter(<AppShell />);
    // desktop header + mobile tab bar each render the links, so use getAllByRole.
    expect(screen.getAllByRole("link", { name: /recipes/i }).length).toBeGreaterThan(0);
    const list = screen.getAllByRole("link", { name: /^list$/i })[0];
    const kroger = screen.getAllByRole("link", { name: /kroger/i })[0];
    expect(list).toHaveAttribute("href", "/list");
    expect(kroger).toHaveAttribute("href", "/kroger");
  });
});

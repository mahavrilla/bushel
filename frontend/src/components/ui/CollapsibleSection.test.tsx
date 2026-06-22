import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CollapsibleSection } from "./CollapsibleSection";

afterEach(() => vi.restoreAllMocks());

describe("CollapsibleSection", () => {
  it("is collapsed by default and toggles open", async () => {
    render(
      <CollapsibleSection title="On this list">
        <p>body content</p>
      </CollapsibleSection>,
    );
    const toggle = screen.getByRole("button", { name: /on this list/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("body content")).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("body content")).toBeInTheDocument();
  });
});

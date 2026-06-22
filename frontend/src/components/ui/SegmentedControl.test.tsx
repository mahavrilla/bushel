import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SegmentedControl } from "./SegmentedControl";

afterEach(() => vi.restoreAllMocks());

const opts = [
  { value: "items", label: "Items" },
  { value: "cart", label: "Cart" },
] as const;

describe("SegmentedControl", () => {
  it("marks the active option and fires onChange", async () => {
    const onChange = vi.fn();
    render(<SegmentedControl options={[...opts]} value="items" onChange={onChange} />);
    expect(screen.getByRole("tab", { name: "Items" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Cart" })).toHaveAttribute("aria-selected", "false");
    await userEvent.click(screen.getByRole("tab", { name: "Cart" }));
    expect(onChange).toHaveBeenCalledWith("cart");
  });
});

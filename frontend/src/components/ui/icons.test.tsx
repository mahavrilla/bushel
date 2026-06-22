import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BasketIcon, BookIcon, CartIcon, CloseIcon } from "./icons";

describe("icons", () => {
  it("render as decorative svgs with the given size", () => {
    const { container } = render(
      <div>
        <BookIcon />
        <BasketIcon />
        <CartIcon />
        <CloseIcon />
      </div>,
    );
    const svgs = container.querySelectorAll("svg");
    expect(svgs).toHaveLength(4);
    svgs.forEach((svg) => {
      expect(svg).toHaveAttribute("aria-hidden", "true");
      expect(svg).toHaveAttribute("width", "24");
    });
  });
});

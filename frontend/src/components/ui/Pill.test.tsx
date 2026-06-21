import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Pill } from "./Pill";

describe("Pill", () => {
  it("renders its label and tone class", () => {
    render(<Pill tone="success">In stock</Pill>);
    const el = screen.getByText("In stock");
    expect(el).toBeInTheDocument();
    expect(el.className).toContain("text-success");
  });
});

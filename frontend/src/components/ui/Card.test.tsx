import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card } from "./Card";

describe("Card", () => {
  it("renders children inside a surface container", () => {
    render(<Card>hello</Card>);
    const el = screen.getByText("hello");
    expect(el.className).toContain("bg-surface");
  });
});

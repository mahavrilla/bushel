import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Spinner } from "./Spinner";

describe("Spinner", () => {
  it("renders an accessible loading indicator", () => {
    render(<Spinner />);
    expect(screen.getByRole("status", { name: /loading/i })).toBeInTheDocument();
  });
});

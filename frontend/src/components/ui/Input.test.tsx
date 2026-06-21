import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Input } from "./Input";

describe("Input", () => {
  it("associates its label and forwards changes", async () => {
    const onChange = vi.fn();
    render(<Input label="Zip code" value="" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText(/zip code/i), "4");
    expect(onChange).toHaveBeenCalled();
  });
});

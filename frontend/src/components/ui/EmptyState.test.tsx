import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows a message and fires the optional action", async () => {
    const onAction = vi.fn();
    render(<EmptyState icon="🧺" message="No recipes yet" actionLabel="Add one" onAction={onAction} />);
    expect(screen.getByText(/no recipes yet/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /add one/i }));
    expect(onAction).toHaveBeenCalledOnce();
  });
});

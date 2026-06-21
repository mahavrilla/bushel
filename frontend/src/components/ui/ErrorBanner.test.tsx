import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ErrorBanner } from "./ErrorBanner";

describe("ErrorBanner", () => {
  it("renders an alert with optional action", async () => {
    const onAction = vi.fn();
    render(<ErrorBanner message="Session expired" actionLabel="Reconnect" onAction={onAction} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/session expired/i);
    await userEvent.click(screen.getByRole("button", { name: /reconnect/i }));
    expect(onAction).toHaveBeenCalledOnce();
  });
});

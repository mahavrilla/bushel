import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { StaplesSection } from "./StaplesSection";

afterEach(() => vi.restoreAllMocks());

const view = {
  staples: [
    { id: 1, ingredient_id: 2, ingredient_name: "peanut butter", auto_add: true, on_trip: true },
    { id: 2, ingredient_id: 3, ingredient_name: "rice", auto_add: false, on_trip: false },
  ],
};

describe("StaplesSection", () => {
  it("lists staples with on-trip state", async () => {
    vi.spyOn(api, "getStaples").mockResolvedValue(view);
    render(<StaplesSection onChange={() => {}} />);
    expect(await screen.findByText(/peanut butter/)).toBeInTheDocument();
    expect(screen.getByText(/rice/)).toBeInTheDocument();
  });

  it("adds a staple by name", async () => {
    vi.spyOn(api, "getStaples").mockResolvedValue(view);
    const add = vi.spyOn(api, "addStaple").mockResolvedValue(view);
    render(<StaplesSection onChange={() => {}} />);
    fireEvent.change(await screen.findByLabelText(/add a staple/i), { target: { value: "butter" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));
    await waitFor(() => expect(add).toHaveBeenCalledWith("butter"));
  });

  it("toggling a not-on-trip staple adds it to the trip", async () => {
    vi.spyOn(api, "getStaples").mockResolvedValue(view);
    const addTrip = vi.spyOn(api, "addStapleToTrip").mockResolvedValue(view);
    const onChange = vi.fn();
    render(<StaplesSection onChange={onChange} />);
    const riceToggle = await screen.findByLabelText(/include rice/i);
    fireEvent.click(riceToggle);
    await waitFor(() => expect(addTrip).toHaveBeenCalledWith(2));
    expect(onChange).toHaveBeenCalled();
  });
});

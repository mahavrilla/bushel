import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ProductPickerModal } from "./ProductPickerModal";
import type { ProductChoice } from "./types";

afterEach(() => vi.restoreAllMocks());

function p(over: Partial<ProductChoice> & { upc: string }): ProductChoice {
  return {
    description: "desc",
    size: null,
    price: null,
    stock_level: null,
    ...over,
  };
}

describe("ProductPickerModal", () => {
  it("searches with the ingredient name on open", async () => {
    const search = vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      p({ upc: "1", description: "Jif Creamy", brand: "Jif" }),
    ]);
    render(<ProductPickerModal itemId={5} ingredientName="peanut butter" onChoose={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(search).toHaveBeenCalledWith(5, "peanut butter", 0, 24));
    expect(await screen.findByText(/Jif Creamy/)).toBeInTheDocument();
  });

  it("re-searches from the start when the term is edited", async () => {
    const search = vi
      .spyOn(api, "searchItemProducts")
      .mockResolvedValueOnce([p({ upc: "1", description: "old" })])
      .mockResolvedValueOnce([p({ upc: "2", description: "new result" })]);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("old");
    const box = screen.getByRole("searchbox", { name: /search products/i });
    await userEvent.clear(box);
    await userEvent.type(box, "jif natural");
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(5, "jif natural", 0, 24));
    expect(await screen.findByText("new result")).toBeInTheDocument();
    expect(screen.queryByText("old")).not.toBeInTheDocument();
  });

  it("loads more and de-dupes by upc", async () => {
    const page1 = Array.from({ length: 24 }, (_, i) => p({ upc: `a${i}`, description: `prod ${i}` }));
    const page2 = [p({ upc: "a0", description: "prod 0" }), p({ upc: "z", description: "fresh item" })];
    const search = vi
      .spyOn(api, "searchItemProducts")
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("prod 0");
    fireEvent.click(await screen.findByRole("button", { name: /load more/i }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(5, "pb", 24, 24));
    expect(await screen.findByText("fresh item")).toBeInTheDocument();
    expect(screen.getAllByText("prod 0")).toHaveLength(1); // a0 not duplicated
  });

  it("hides out-of-stock items when 'In stock only' is checked", async () => {
    vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      p({ upc: "1", description: "in stock", stock_level: "HIGH" }),
      p({ upc: "2", description: "out of stock", stock_level: "TEMPORARILY_OUT_OF_STOCK" }),
    ]);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("out of stock");
    await userEvent.click(screen.getByRole("checkbox", { name: /in stock only/i }));
    expect(screen.queryByText("out of stock")).not.toBeInTheDocument();
    expect(screen.getByText("in stock")).toBeInTheDocument();
  });

  it("sorts by price ascending", async () => {
    vi.spyOn(api, "searchItemProducts").mockResolvedValue([
      p({ upc: "1", description: "pricey", price: 9 }),
      p({ upc: "2", description: "cheap", price: 2 }),
    ]);
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText("pricey");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /sort/i }), "price");
    const descs = screen.getAllByTestId("product-desc").map((n) => n.textContent);
    expect(descs).toEqual(["cheap", "pricey"]);
  });

  it("calls onChoose with the product", async () => {
    vi.spyOn(api, "searchItemProducts").mockResolvedValue([p({ upc: "1", description: "Jif" })]);
    const onChoose = vi.fn();
    render(<ProductPickerModal itemId={5} ingredientName="pb" onChoose={onChoose} onClose={vi.fn()} />);
    await screen.findByText("Jif");
    await userEvent.click(screen.getByRole("button", { name: /choose/i }));
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ upc: "1", description: "Jif" }));
  });
});

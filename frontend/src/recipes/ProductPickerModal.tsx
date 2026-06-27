import { useEffect, useState } from "react";

import { ApiError, searchItemProducts } from "../api";
import { Button } from "../components/ui/Button";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import type { ProductChoice } from "./types";

const PAGE = 24;

function dedupe(products: ProductChoice[]): ProductChoice[] {
  const seen = new Set<string>();
  const out: ProductChoice[] = [];
  for (const item of products) {
    if (seen.has(item.upc)) continue;
    seen.add(item.upc);
    out.push(item);
  }
  return out;
}

export function ProductPickerModal({
  itemId,
  ingredientName,
  onChoose,
  onClose,
  title = "Choose a product",
  chooseLabel = "Choose",
}: {
  itemId: number;
  ingredientName: string | null;
  onChoose: (product: ProductChoice) => void | Promise<void>;
  onClose: () => void;
  title?: string;
  chooseLabel?: string;
}) {
  const [query, setQuery] = useState(ingredientName ?? "");
  const [results, setResults] = useState<ProductChoice[]>([]);
  const [start, setStart] = useState(0);
  const [reachedEnd, setReachedEnd] = useState(false);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [sort, setSort] = useState<"relevance" | "price">("relevance");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(reset: boolean) {
    const from = reset ? 0 : start;
    setLoading(true);
    setError(null);
    try {
      const page = await searchItemProducts(itemId, query.trim(), from, PAGE);
      setResults((prev) => (reset ? page : dedupe([...prev, ...page])));
      setStart(from + PAGE);
      setReachedEnd(page.length < PAGE);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? "Pick a home store first (on the Kroger tab), then try again."
          : "Something went wrong searching products. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // itemId/ingredientName are fixed for the modal's lifetime; search once on open.
    run(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    run(true);
  }

  let view = results;
  if (inStockOnly) view = view.filter((x) => x.stock_level !== "TEMPORARILY_OUT_OF_STOCK");
  if (sort === "price") view = [...view].sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={onSubmit} className="mb-3 flex items-end gap-2">
        <Input
          type="search"
          label="Search products"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full"
        />
        <Button type="submit">Search</Button>
      </form>

      <div className="mb-3 flex items-center gap-4 text-sm">
        <label className="flex items-center gap-2 text-ink">
          <input
            type="checkbox"
            checked={inStockOnly}
            onChange={(e) => setInStockOnly(e.target.checked)}
          />
          In stock only
        </label>
        <label className="ml-auto flex items-center gap-2 text-ink">
          Sort
          <select
            aria-label="Sort"
            className="rounded-xl border border-line bg-surface px-2 py-1"
            value={sort}
            onChange={(e) => setSort(e.target.value as "relevance" | "price")}
          >
            <option value="relevance">Relevance</option>
            <option value="price">Price: low to high</option>
          </select>
        </label>
      </div>

      {error && <ErrorBanner message={error} />}

      <ul className="flex flex-col gap-2">
        {view.map((item) => (
          <li key={item.upc} className="flex items-center gap-3 rounded-xl border border-line p-2">
            {item.image_url && (
              <img
                src={item.image_url}
                alt={item.description}
                className="h-14 w-14 shrink-0 rounded object-contain"
              />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                {item.brand && <span className="text-sm font-semibold text-heading">{item.brand}</span>}
                <span className="text-sm text-ink" data-testid="product-desc">
                  {item.description}
                </span>
                {item.stock_level === "TEMPORARILY_OUT_OF_STOCK" && <Pill tone="danger">Out of stock</Pill>}
              </div>
              <div className="text-sm text-muted">
                {item.size}
                {item.price != null && ` · $${item.price.toFixed(2)}`}
              </div>
            </div>
            <Button variant="secondary" onClick={() => onChoose(item)}>
              {chooseLabel}
            </Button>
          </li>
        ))}
      </ul>

      {loading && (
        <div className="flex justify-center py-4">
          <Spinner />
        </div>
      )}
      {!loading && !reachedEnd && results.length > 0 && (
        <div className="mt-3 flex justify-center">
          <Button variant="secondary" onClick={() => run(false)} disabled={loading}>
            Load more
          </Button>
        </div>
      )}
    </Modal>
  );
}

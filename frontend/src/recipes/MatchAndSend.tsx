import { useEffect, useState } from "react";

import { ApiError, confirmProduct, getMatch, searchItemProducts, sendCart } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import type { MatchData, ProductChoice, SendResult } from "./types";

export function MatchAndSend() {
  const [match, setMatch] = useState<MatchData | null>(null);
  const [choices, setChoices] = useState<Record<number, ProductChoice[]>>({});
  const [modality, setModality] = useState("PICKUP");
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMatch().then(setMatch).catch(() => setMatch(null));
  }, []);

  function report(err: unknown) {
    if (err instanceof ApiError && err.status === 409) {
      setError("Your Kroger session expired — reconnect on the Kroger tab, then try again.");
    } else {
      setError("Something went wrong talking to Kroger. Please try again.");
    }
  }

  async function find(itemId: number, name: string | null) {
    setError(null);
    try {
      const results = await searchItemProducts(itemId, name ?? "");
      setChoices((c) => ({ ...c, [itemId]: results }));
    } catch (err) {
      report(err);
    }
  }

  async function pick(itemId: number, p: ProductChoice) {
    setError(null);
    try {
      setMatch(
        await confirmProduct(itemId, {
          kroger_upc: p.upc,
          kroger_description: p.description,
          package_size: p.size,
        }),
      );
    } catch (err) {
      report(err);
    }
  }

  async function send() {
    setError(null);
    try {
      setSendResult(await sendCart(modality));
      setMatch(await getMatch());
    } catch (err) {
      report(err);
    }
  }

  if (!match)
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Review &amp; send</h3>
      {error && <ErrorBanner message={error} />}
      {!match.connected && <p className="text-sm text-muted">Connect your Kroger account first.</p>}
      {!match.store_location_id && <p className="text-sm text-muted">Pick a home store first.</p>}

      <ul className="flex flex-col gap-3">
        {match.items.map((it) => (
          <li key={it.item_id} className="rounded-xl border border-line p-3">
            <div className="flex flex-wrap items-center gap-2">
              <strong className="text-heading">{it.ingredient_name}</strong>
              <span className="text-sm text-muted">
                need {it.total_qty ?? "?"} {it.total_unit ?? ""}; buy {it.purchase_qty}
              </span>
              {it.purchase_qty_estimated && <Pill tone="warning">Check quantity</Pill>}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-ink">
                {it.current ? `Product: ${it.current.description}` : "No product chosen"}
              </span>
              <Button variant="secondary" className="ml-auto" onClick={() => find(it.item_id, it.ingredient_name)}>
                Find product
              </Button>
            </div>
            <ul className="mt-2 flex flex-col gap-1">
              {(choices[it.item_id] ?? []).map((p) => (
                <li key={p.upc} className="flex items-center gap-2 text-sm">
                  <span>{p.description}</span>
                  {p.size && <span className="text-muted">({p.size})</span>}
                  {p.price != null && <span className="text-muted">${p.price.toFixed(2)}</span>}
                  {p.stock_level === "TEMPORARILY_OUT_OF_STOCK" && <Pill tone="danger">Out of stock</Pill>}
                  <Button variant="link" className="ml-auto" onClick={() => pick(it.item_id, p)}>
                    Choose
                  </Button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Modality</span>
          <select
            className="rounded-xl border border-line bg-surface px-3 py-2 text-ink"
            value={modality}
            onChange={(e) => setModality(e.target.value)}
          >
            <option value="PICKUP">Pickup</option>
            <option value="DELIVERY">Delivery</option>
          </select>
        </label>
        <Button className="ml-auto" onClick={send}>
          Send to Kroger cart
        </Button>
      </div>

      {sendResult && (
        <div className="rounded-xl bg-cream p-3">
          <p className="text-sm font-medium text-heading">Status: {sendResult.status}</p>
          <ul className="mt-1 flex flex-col gap-1">
            {sendResult.results.map((r) => (
              <li key={r.upc} className="text-sm">
                {r.upc}: {r.ok ? "added" : `failed — ${r.error}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

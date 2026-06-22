import { useEffect, useState } from "react";

import { ApiError, confirmProduct, getMatch, sendCart, setPantryDecision } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Pill } from "../components/ui/Pill";
import { Spinner } from "../components/ui/Spinner";
import { TrashIcon } from "../components/ui/icons";
import { ProductPickerModal } from "./ProductPickerModal";
import type { MatchData, MatchItem, ProductChoice, SendResult } from "./types";

export function CartTab() {
  const [match, setMatch] = useState<MatchData | null>(null);
  const [openItem, setOpenItem] = useState<MatchItem | null>(null);
  const [modality, setModality] = useState("PICKUP");
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getMatch().then(setMatch).catch(() => setMatch(null));
  }
  useEffect(load, []);

  function report(err: unknown) {
    setError(
      err instanceof ApiError && err.status === 409
        ? "Your Kroger session expired — reconnect on the Kroger tab, then try again."
        : "Something went wrong talking to Kroger. Please try again.",
    );
  }

  async function pick(product: ProductChoice) {
    if (openItem === null) return;
    setError(null);
    try {
      setMatch(
        await confirmProduct(openItem.item_id, {
          kroger_upc: product.upc,
          kroger_description: product.description,
          package_size: product.size,
        }),
      );
    } catch (err) {
      report(err);
    } finally {
      setOpenItem(null);
    }
  }

  async function remove(item: MatchItem) {
    setError(null);
    try {
      await setPantryDecision(item.item_id, false);
      load();
    } catch (err) {
      report(err);
    }
  }

  async function send() {
    setError(null);
    try {
      setSendResult(await sendCart(modality));
      load();
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

  const confirmed = match.items.filter((it) => it.current !== null);
  const needs = match.items.filter((it) => it.current === null);

  function row(it: MatchItem) {
    return (
      <li key={it.item_id} className="flex items-start justify-between gap-3 rounded-2xl border border-line bg-surface p-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-semibold text-heading">
            {it.ingredient_name}
            {it.current && <span className="text-success" aria-hidden="true">✓</span>}
            {it.purchase_qty_estimated && <Pill tone="warning">Check qty</Pill>}
          </p>
          {it.current ? (
            <p className="text-sm text-muted">
              {it.current.description}
              {it.current.size ? ` (${it.current.size})` : ""} · buy {it.purchase_qty}
            </p>
          ) : (
            <p className="text-sm text-muted">need {it.total_qty ?? "?"} {it.total_unit ?? ""}</p>
          )}
          <Button variant="link" className="px-0" onClick={() => setOpenItem(it)}>
            {it.current ? "Change" : "Choose product →"}
          </Button>
        </div>
        <button
          type="button"
          aria-label={`Remove ${it.ingredient_name}`}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-danger"
          onClick={() => remove(it)}
        >
          <TrashIcon size={18} />
        </button>
      </li>
    );
  }

  return (
    <Card className="flex flex-col gap-3">
      {error && <ErrorBanner message={error} />}
      {!match.connected && <p className="text-sm text-muted">Connect your Kroger account first.</p>}
      {!match.store_location_id && <p className="text-sm text-muted">Pick a home store first.</p>}

      {confirmed.length > 0 && (
        <>
          <p className="text-xs font-bold uppercase tracking-wide text-muted">Confirmed · {confirmed.length}</p>
          <ul className="flex flex-col gap-2">{confirmed.map(row)}</ul>
        </>
      )}
      {needs.length > 0 && (
        <>
          <p className="text-xs font-bold uppercase tracking-wide text-muted">Needs a product · {needs.length}</p>
          <ul className="flex flex-col gap-2">{needs.map(row)}</ul>
        </>
      )}
      {match.items.length === 0 && <p className="text-sm text-muted">Nothing to send yet.</p>}

      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-heading">Fulfillment</span>
          <select
            className="min-h-[44px] rounded-lg border border-line-strong bg-surface px-3 py-2 text-ink"
            value={modality}
            onChange={(e) => setModality(e.target.value)}
          >
            <option value="PICKUP">Pickup</option>
            <option value="DELIVERY">Delivery</option>
          </select>
        </label>
        <Button className="ml-auto" onClick={send}>
          Send to cart
        </Button>
      </div>

      {sendResult && (
        <div className="rounded-xl bg-canvas p-3">
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

      {openItem && (
        <ProductPickerModal
          key={openItem.item_id}
          itemId={openItem.item_id}
          ingredientName={openItem.ingredient_name}
          onChoose={pick}
          onClose={() => setOpenItem(null)}
        />
      )}
    </Card>
  );
}

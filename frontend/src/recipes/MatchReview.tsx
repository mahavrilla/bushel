import { useEffect, useState } from "react";

import { confirmProduct, getMatch, searchItemProducts, sendCart } from "../api";
import type { MatchData, ProductChoice, SendResult } from "./types";

export function MatchReview() {
  const [match, setMatch] = useState<MatchData | null>(null);
  const [choices, setChoices] = useState<Record<number, ProductChoice[]>>({});
  const [modality, setModality] = useState("PICKUP");
  const [sendResult, setSendResult] = useState<SendResult | null>(null);

  useEffect(() => {
    getMatch().then(setMatch).catch(() => setMatch(null));
  }, []);

  async function find(itemId: number, name: string | null) {
    const results = await searchItemProducts(itemId, name ?? "");
    setChoices((c) => ({ ...c, [itemId]: results }));
  }

  async function pick(itemId: number, p: ProductChoice) {
    setMatch(
      await confirmProduct(itemId, {
        kroger_upc: p.upc,
        kroger_description: p.description,
        package_size: p.size,
      }),
    );
  }

  async function send() {
    setSendResult(await sendCart(modality));
    setMatch(await getMatch());
  }

  if (!match) return <p>Loading…</p>;

  return (
    <section>
      <h2>Match &amp; send</h2>
      {!match.connected && <p>Connect your Kroger account first.</p>}
      {!match.store_location_id && <p>Pick a home store first.</p>}

      <ul>
        {match.items.map((it) => (
          <li key={it.item_id}>
            <strong>{it.ingredient_name}</strong> — need{" "}
            {it.total_qty ?? "?"} {it.total_unit ?? ""}; buy {it.purchase_qty}{" "}
            {it.purchase_qty_estimated && <em>(check quantity)</em>}
            <div>
              {it.current ? (
                <span>Product: {it.current.description}</span>
              ) : (
                <span>No product chosen</span>
              )}
              <button onClick={() => find(it.item_id, it.ingredient_name)}>Find product</button>
            </div>
            <ul>
              {(choices[it.item_id] ?? []).map((p) => (
                <li key={p.upc}>
                  {p.description} {p.size ? `(${p.size})` : ""}{" "}
                  {p.price != null ? `$${p.price.toFixed(2)}` : ""}{" "}
                  {p.stock_level === "TEMPORARILY_OUT_OF_STOCK" && <em>out of stock</em>}
                  <button onClick={() => pick(it.item_id, p)}>Choose</button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      <label>
        Modality
        <select value={modality} onChange={(e) => setModality(e.target.value)}>
          <option value="PICKUP">Pickup</option>
          <option value="DELIVERY">Delivery</option>
        </select>
      </label>
      <button onClick={send}>Send to Kroger cart</button>

      {sendResult && (
        <div>
          <p>Status: {sendResult.status}</p>
          <ul>
            {sendResult.results.map((r) => (
              <li key={r.upc}>
                {r.upc}: {r.ok ? "added" : `failed — ${r.error}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

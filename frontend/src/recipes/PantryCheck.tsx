import { useEffect, useState } from "react";

import { getPantry, setPantryDecision } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Pill } from "../components/ui/Pill";
import type { PantryView } from "./types";

export function PantryCheck() {
  const [view, setView] = useState<PantryView | null>(null);

  useEffect(() => {
    getPantry().then(setView).catch(() => setView(null));
  }, []);

  async function decide(itemId: number, keep: boolean) {
    setView(await setPantryDecision(itemId, keep));
  }

  if (!view) return null;

  const flagged = view.items.filter((i) => i.pantry_status === "maybe_have");
  const skipped = view.items.filter((i) => i.pantry_status === "skipped");

  if (flagged.length === 0 && skipped.length === 0) {
    return <span data-testid="pantry-empty" className="hidden" />;
  }

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Still have it?</h3>
      <ul className="flex flex-col gap-2">
        {flagged.map((i) => (
          <li key={i.item_id} className="flex flex-wrap items-center gap-2 rounded-xl bg-tint-amber px-3 py-2">
            <strong className="text-heading">{i.ingredient_name}</strong>
            <span className="text-sm text-ink">
              bought {i.last_qty ?? "?"} {i.last_unit ?? ""}, {i.days_ago} days ago
            </span>
            <span className="ml-auto flex gap-2">
              <Button variant="secondary" onClick={() => decide(i.item_id, true)}>Keep</Button>
              <Button variant="link" onClick={() => decide(i.item_id, false)}>I have it</Button>
            </span>
          </li>
        ))}
      </ul>
      {skipped.length > 0 && (
        <div className="text-sm text-muted">
          <span className="font-medium">Skipping (already have): </span>
          {skipped.map((i, idx) => (
            <span key={i.item_id}>
              {idx > 0 && ", "}
              {i.ingredient_name}
              <button className="ml-1 text-primary underline" onClick={() => decide(i.item_id, true)}>
                undo
              </button>
            </span>
          ))}
        </div>
      )}
      {flagged.length > 0 && <Pill tone="warning">Decide before sending to keep them in your cart</Pill>}
    </Card>
  );
}

import { useEffect, useState } from "react";

import {
  addStaple, addStapleToTrip, getStaples, removeStaple, removeStapleFromTrip, setStapleAutoAdd,
} from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import type { StapleView } from "./types";

export function StaplesSection({ onChange }: { onChange: () => void }) {
  const [view, setView] = useState<StapleView | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStaples().then(setView).catch(() => setView(null));
  }, []);

  // Every staples mutation refreshes both this section and the parent grocery list.
  function apply(next: StapleView) {
    setView(next);
    onChange();
  }

  async function add() {
    if (!name.trim()) return;
    setError(null);
    try {
      apply(await addStaple(name.trim()));
      setName("");
    } catch {
      setError("Couldn't add that staple — please try again.");
    }
  }

  async function toggleTrip(id: number, onTrip: boolean) {
    setError(null);
    try {
      apply(onTrip ? await removeStapleFromTrip(id) : await addStapleToTrip(id));
    } catch {
      setError("Couldn't update the trip — please try again.");
    }
  }

  async function toggleAuto(id: number, autoAdd: boolean) {
    setError(null);
    try {
      // auto-add affects future trips, not the current shopping list — no parent refresh.
      setView(await setStapleAutoAdd(id, autoAdd));
    } catch {
      setError("Couldn't update auto-add — please try again.");
    }
  }

  async function remove(id: number) {
    setError(null);
    try {
      apply(await removeStaple(id));
    } catch {
      setError("Couldn't remove that staple — please try again.");
    }
  }

  if (!view) return null;

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Staples</h3>
      {error && <ErrorBanner message={error} />}
      <ul className="flex flex-col gap-1">
        {view.staples.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                aria-label={`Include ${s.ingredient_name ?? "item"}`}
                checked={s.on_trip}
                onChange={() => toggleTrip(s.id, s.on_trip)}
              />
              <span className="text-heading">{s.ingredient_name ?? "item"}</span>
            </label>
            <label className="ml-auto flex items-center gap-1 text-xs text-muted">
              <input
                type="checkbox"
                aria-label={`Auto-add ${s.ingredient_name ?? "item"}`}
                checked={s.auto_add}
                onChange={() => toggleAuto(s.id, !s.auto_add)}
              />
              auto-add
            </label>
            <Button variant="link" onClick={() => remove(s.id)}>remove</Button>
          </li>
        ))}
      </ul>
      <div className="flex items-end gap-2">
        <Input label="Add a staple" value={name} onChange={(e) => setName(e.target.value)} className="w-48" />
        <Button variant="secondary" onClick={add}>Add</Button>
      </div>
    </Card>
  );
}

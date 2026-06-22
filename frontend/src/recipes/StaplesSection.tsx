import { useEffect, useState } from "react";

import {
  addStaple, addStapleToTrip, getStaples, removeStaple, removeStapleFromTrip, setStapleAutoAdd,
} from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import type { StapleView } from "./types";

export function StaplesSection({ onChange }: { onChange: () => void }) {
  const [view, setView] = useState<StapleView | null>(null);
  const [name, setName] = useState("");

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
    apply(await addStaple(name.trim()));
    setName("");
  }

  async function toggleTrip(id: number, onTrip: boolean) {
    apply(onTrip ? await removeStapleFromTrip(id) : await addStapleToTrip(id));
  }

  async function toggleAuto(id: number, autoAdd: boolean) {
    setView(await setStapleAutoAdd(id, autoAdd));
  }

  async function remove(id: number) {
    apply(await removeStaple(id));
  }

  if (!view) return null;

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold text-heading">Staples</h3>
      <ul className="flex flex-col gap-1">
        {view.staples.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                aria-label={`Include ${s.ingredient_name}`}
                checked={s.on_trip}
                onChange={() => toggleTrip(s.id, s.on_trip)}
              />
              <span className="text-heading">{s.ingredient_name}</span>
            </label>
            <label className="ml-auto flex items-center gap-1 text-xs text-muted">
              <input
                type="checkbox"
                aria-label={`Auto-add ${s.ingredient_name}`}
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

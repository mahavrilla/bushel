import { useEffect, useState } from "react";

import { createIngredient, searchIngredients } from "../api";
import { Button } from "../components/ui/Button";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import type { IngredientOption } from "./types";

export function IngredientPicker({ onPick }: { onPick: (ingredientId: number) => void }) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<IngredientOption[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setOptions([]);
      return;
    }
    let active = true;
    searchIngredients(q)
      .then((opts) => active && setOptions(opts))
      .catch(() => active && setOptions([]));
    return () => {
      active = false;
    };
  }, [query]);

  async function create() {
    setError(null);
    try {
      const opt = await createIngredient(query.trim());
      onPick(opt.id);
    } catch {
      setError("Couldn't create ingredient — please try again.");
    }
  }

  const trimmed = query.trim();

  return (
    <div className="mt-2 flex flex-col gap-1 rounded-xl border border-line p-2">
      <Input
        type="search"
        label="Find ingredient"
        placeholder="Search ingredients…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {error && <ErrorBanner message={error} />}
      <ul className="flex flex-col" aria-label="Ingredient options">
        {options.map((o) => (
          <li key={o.id}>
            <Button variant="link" onClick={() => onPick(o.id)}>
              {o.canonical_name}
            </Button>
          </li>
        ))}
        {trimmed && (
          <li>
            <Button variant="link" onClick={create}>
              Create "{trimmed}"
            </Button>
          </li>
        )}
      </ul>
    </div>
  );
}

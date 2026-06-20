import { useState } from "react";

import { createRecipe, importRecipe } from "../api";

export function AddRecipe({ onCreated }: { onCreated: (id: number) => void }) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [servings, setServings] = useState(1);
  const [lines, setLines] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<{ id: number }>) {
    setBusy(true);
    setError(null);
    try {
      const recipe = await action();
      onCreated(recipe.id);
    } catch {
      setError("Couldn't import — check the URL or try manual entry.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <section>
        <h2>Import by URL</h2>
        <label>
          Recipe URL
          <input value={url} onChange={(e) => setUrl(e.target.value)} />
        </label>
        <button disabled={busy || !url} onClick={() => run(() => importRecipe(url))}>
          {busy ? "Importing…" : "Import"}
        </button>
      </section>

      <section>
        <h2>Or enter manually</h2>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Servings
          <input
            type="number"
            value={servings}
            onChange={(e) => setServings(Number(e.target.value))}
          />
        </label>
        <label>
          Ingredients (one per line)
          <textarea value={lines} onChange={(e) => setLines(e.target.value)} />
        </label>
        <button
          disabled={busy || !title.trim() || !lines.trim()}
          onClick={() =>
            run(() => createRecipe(title, servings, lines.split("\n")))
          }
        >
          {busy ? "Saving…" : "Save recipe"}
        </button>
      </section>

      {error && <p role="alert">{error}</p>}
    </div>
  );
}

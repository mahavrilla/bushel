import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createRecipe, extractIngredients, importRecipe } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";

export function AddRecipe() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"url" | "manual">("url");
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
      navigate(`/recipes/${recipe.id}`);
    } catch {
      setError("Couldn't import — check the URL or try manual entry.");
    } finally {
      setBusy(false);
    }
  }

  async function extract() {
    setBusy(true);
    setError(null);
    try {
      const extracted = await extractIngredients(lines);
      setLines(extracted.join("\n"));
    } catch {
      setError("Couldn't extract ingredients — edit manually or try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Add recipe" />
      <SegmentedControl
        options={[
          { value: "url", label: "URL" },
          { value: "manual", label: "Manual" },
        ]}
        value={mode}
        onChange={setMode}
      />
      {error && <ErrorBanner message={error} />}

      {mode === "url" ? (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Import by URL</h3>
          <Input label="Recipe URL" value={url} onChange={(e) => setUrl(e.target.value)} />
          <Button disabled={!url} loading={busy} className="self-start" onClick={() => run(() => importRecipe(url))}>
            Import
          </Button>
        </Card>
      ) : (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Enter manually</h3>
          <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input
            label="Servings"
            type="number"
            value={servings}
            onChange={(e) => setServings(Number(e.target.value))}
          />
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor="ingredients" className="font-medium text-heading">
              Ingredients
            </label>
            <p id="ingredients-hint" className="text-xs text-muted">
              Paste a full recipe and click Extract, or enter one ingredient per line.
            </p>
            <textarea
              id="ingredients"
              aria-describedby="ingredients-hint"
              className="min-h-24 rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              value={lines}
              onChange={(e) => setLines(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={!lines.trim()}
              loading={busy}
              className="self-start"
              onClick={extract}
            >
              Extract ingredients
            </Button>
            <Button
              disabled={!title.trim() || !lines.trim()}
              loading={busy}
              className="self-start"
              onClick={() => run(() => createRecipe(title, servings, lines.split("\n")))}
            >
              Save recipe
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

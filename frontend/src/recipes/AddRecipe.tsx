import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createRecipe, extractIngredients, importPhotoRecipe, importRecipe } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { CloseIcon } from "../components/ui/icons";

const IMPORT_ERROR = "Couldn't import — check the URL or try manual entry.";
const PHOTO_ERROR = "Couldn't read those photos — try a clearer photo or enter it manually.";

export function AddRecipe() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"url" | "manual" | "photo">("url");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [servings, setServings] = useState(1);
  const [lines, setLines] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const previews = useMemo(
    () => photos.map((file) => ({ file, url: URL.createObjectURL(file) })),
    [photos],
  );
  useEffect(() => () => previews.forEach((p) => URL.revokeObjectURL(p.url)), [previews]);

  async function run(action: () => Promise<{ id: number }>, errorMessage = IMPORT_ERROR) {
    setBusy(true);
    setError(null);
    try {
      const recipe = await action();
      navigate(`/recipes/${recipe.id}`);
    } catch {
      setError(errorMessage);
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
          { value: "photo", label: "Photo" },
        ]}
        value={mode}
        onChange={setMode}
      />
      {error && <ErrorBanner message={error} />}

      {mode === "url" && (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Import by URL</h3>
          <Input label="Recipe URL" value={url} onChange={(e) => setUrl(e.target.value)} />
          <Button disabled={!url} loading={busy} className="self-start" onClick={() => run(() => importRecipe(url))}>
            Import
          </Button>
        </Card>
      )}

      {mode === "manual" && (
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

      {mode === "photo" && (
        <Card className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">From a photo</h3>
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor="photos" className="font-medium text-heading">
              Add recipe photos
            </label>
            <p className="text-xs text-muted">
              Snap or pick one or more photos of the recipe. They're read once and not stored.
            </p>
            <input
              id="photos"
              type="file"
              accept="image/*"
              multiple
              className="text-sm"
              onChange={(e) => {
                const chosen = Array.from(e.target.files ?? []);
                if (chosen.length) setPhotos((prev) => [...prev, ...chosen]);
                e.target.value = "";
              }}
            />
          </div>
          {previews.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {previews.map((p, i) => (
                <li key={p.url} className="relative">
                  <img src={p.url} alt={`Photo ${i + 1}`} className="h-20 w-20 rounded-lg object-cover" />
                  <button
                    type="button"
                    aria-label={`Remove photo ${i + 1}`}
                    onClick={() => setPhotos((prev) => prev.filter((_, j) => j !== i))}
                    className="absolute -right-1.5 -top-1.5 rounded-full bg-surface p-0.5 text-muted shadow"
                  >
                    <CloseIcon size={16} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Button
            disabled={photos.length === 0}
            loading={busy}
            className="self-start"
            onClick={() => run(() => importPhotoRecipe(photos), PHOTO_ERROR)}
          >
            Create from photos
          </Button>
        </Card>
      )}
    </div>
  );
}

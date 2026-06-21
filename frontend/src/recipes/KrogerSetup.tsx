import { useEffect, useState } from "react";

import { getKrogerLoginUrl, getKrogerStatus, getMatch, searchLocations, setStore } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import type { KrogerLocation, KrogerStatus } from "./types";

export function KrogerSetup() {
  const [status, setStatus] = useState<KrogerStatus | null>(null);
  const [zip, setZip] = useState("");
  const [stores, setStores] = useState<KrogerLocation[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getKrogerStatus().then(setStatus).catch(() => setStatus(null));
    getMatch().then((m) => setSelected(m.store_location_id)).catch(() => {});
  }, []);

  async function connect() {
    const { url } = await getKrogerLoginUrl();
    window.location.href = url;
  }

  async function findStores() {
    setBusy(true);
    try {
      setStores(await searchLocations(zip));
    } finally {
      setBusy(false);
    }
  }

  async function choose(locationId: string) {
    const match = await setStore(locationId);
    setSelected(match.store_location_id);
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Kroger" />

      <Card>
        {status?.connected ? (
          <p className="text-ink">
            Connected{status.expired ? " — session expired, reconnect below." : "."}
          </p>
        ) : (
          <Button onClick={connect}>Connect Kroger</Button>
        )}
      </Card>

      <Card className="flex flex-col gap-3">
        <h3 className="text-lg font-semibold text-heading">Home store</h3>
        {selected && <p className="text-sm text-success">Selected store: {selected}</p>}
        <div className="flex items-end gap-2">
          <Input label="Zip code" value={zip} onChange={(e) => setZip(e.target.value)} className="w-32" />
          <Button variant="secondary" loading={busy} onClick={findStores}>
            Find stores
          </Button>
        </div>
        <ul className="flex flex-col gap-2">
          {stores.map((s) => (
            <li key={s.location_id} className="flex items-center gap-3 rounded-xl border border-line bg-surface px-3 py-2">
              <div>
                <div className="text-sm font-medium text-heading">{s.name}</div>
                <div className="text-xs text-muted">{s.address}</div>
              </div>
              <Button variant="secondary" className="ml-auto" onClick={() => choose(s.location_id)}>
                Use this store
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

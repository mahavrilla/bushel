import { useEffect, useState } from "react";

import { getKrogerLoginUrl, getKrogerStatus, getMatch, searchLocations, setStore } from "../api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Pill } from "../components/ui/Pill";
import type { KrogerLocation, KrogerStatus } from "./types";

export function KrogerSetup() {
  const [status, setStatus] = useState<KrogerStatus | null>(null);
  const [zip, setZip] = useState("");
  const [stores, setStores] = useState<KrogerLocation[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getKrogerStatus().then(setStatus).catch(() => setStatus(null));
    getMatch().then((m) => setSelectedName(m.store_name ?? null)).catch(() => {});
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

  async function choose(loc: KrogerLocation) {
    const match = await setStore(loc.location_id, loc.name);
    setSelectedName(match.store_name ?? null);
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Kroger" />

      <Card className="flex flex-col gap-3">
        {status?.connected ? (
          status.expired ? (
            <div className="flex items-center gap-3">
              <Pill tone="warning">Session expired</Pill>
              <Button className="ml-auto" onClick={connect}>
                Reconnect
              </Button>
            </div>
          ) : (
            <Pill tone="success">Connected ✓</Pill>
          )
        ) : (
          <Button onClick={connect}>Connect Kroger</Button>
        )}
      </Card>

      <Card className="flex flex-col gap-3">
        <h3 className="text-lg font-semibold text-heading">Home store</h3>
        {selectedName && <p className="text-sm font-medium text-heading">Home store: {selectedName}</p>}
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
              <Button variant="secondary" className="ml-auto" onClick={() => choose(s)}>
                Use this store
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

import { useEffect, useState } from "react";

import { getKrogerLoginUrl, getKrogerStatus, searchLocations } from "../api";
import type { KrogerLocation, KrogerStatus } from "./types";

export function KrogerSetup() {
  const [status, setStatus] = useState<KrogerStatus | null>(null);
  const [zip, setZip] = useState("");
  const [stores, setStores] = useState<KrogerLocation[]>([]);

  useEffect(() => {
    getKrogerStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  async function connect() {
    const { url } = await getKrogerLoginUrl();
    window.location.href = url;
  }

  async function findStores() {
    setStores(await searchLocations(zip));
  }

  return (
    <section>
      <h2>Kroger</h2>
      {status?.connected ? (
        <p>Connected{status.expired ? " (session expired — reconnect)" : ""}.</p>
      ) : (
        <button onClick={connect}>Connect Kroger</button>
      )}

      <h3>Home store</h3>
      <label>
        Zip code
        <input value={zip} onChange={(e) => setZip(e.target.value)} />
      </label>
      <button onClick={findStores}>Find stores</button>
      <ul>
        {stores.map((s) => (
          <li key={s.location_id}>
            {s.name} — {s.address}
          </li>
        ))}
      </ul>
    </section>
  );
}

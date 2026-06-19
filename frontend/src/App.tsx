import { useEffect, useState } from "react";

import { getHealth } from "./api";

export function App() {
  const [status, setStatus] = useState<string>("…");

  useEffect(() => {
    getHealth()
      .then((h) => setStatus(h.status))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <main>
      <h1>Bushel</h1>
      <p>Backend: {status}</p>
    </main>
  );
}

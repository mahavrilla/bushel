import { afterEach, describe, expect, it, vi } from "vitest";

import { confirmProduct, getKrogerStatus, getMatch, searchItemProducts, sendCart } from "../api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown, ok = true) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok,
    status: ok ? 200 : 409,
    json: async () => body,
  } as Response);
}

describe("kroger api", () => {
  it("getKrogerStatus calls /kroger/status", async () => {
    const f = mockFetch({ connected: true, expired: false });
    const res = await getKrogerStatus();
    expect(res.connected).toBe(true);
    expect(f.mock.calls[0][0]).toContain("/kroger/status");
  });

  it("getMatch calls /list/match", async () => {
    const f = mockFetch({ connected: true, store_location_id: "L1", items: [] });
    await getMatch();
    expect(f.mock.calls[0][0]).toContain("/list/match");
  });

  it("searchItemProducts hits the per-item products endpoint", async () => {
    const f = mockFetch([{ upc: "0001", description: "Flour" }]);
    const res = await searchItemProducts(5, "flour");
    expect(res[0].upc).toBe("0001");
    expect(f.mock.calls[0][0]).toContain("/list/items/5/products?q=flour");
  });

  it("confirmProduct POSTs the chosen product", async () => {
    const f = mockFetch({ connected: true, store_location_id: "L1", items: [] });
    await confirmProduct(5, { kroger_upc: "0001", package_size: "1 lb" });
    expect(f.mock.calls[0][1]?.method).toBe("POST");
  });

  it("sendCart POSTs modality", async () => {
    const f = mockFetch({ status: "sent_to_kroger", results: [] });
    await sendCart("PICKUP");
    const body = JSON.parse((f.mock.calls[0][1]?.body as string) ?? "{}");
    expect(body.modality).toBe("PICKUP");
  });
});

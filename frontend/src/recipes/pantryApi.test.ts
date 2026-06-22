import { afterEach, describe, expect, it, vi } from "vitest";

import { setPantryDecision } from "../api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  } as Response);
}

describe("pantry api", () => {
  it("setPantryDecision POSTs keep", async () => {
    const f = mockFetch({ items: [] });
    await setPantryDecision(5, false);
    expect(f.mock.calls[0][0]).toContain("/list/items/5/pantry");
    const body = JSON.parse((f.mock.calls[0][1]?.body as string) ?? "{}");
    expect(body.keep).toBe(false);
  });
});

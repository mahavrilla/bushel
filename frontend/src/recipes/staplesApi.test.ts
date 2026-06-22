import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addStaple, addStapleToTrip, getStaples, removeStaple, removeStapleFromTrip, setStapleAutoAdd,
} from "../api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response);
}

describe("staples api", () => {
  it("getStaples GETs /list/staples", async () => {
    const f = mockFetch({ staples: [] });
    await getStaples();
    expect(f.mock.calls[0][0]).toContain("/list/staples");
  });
  it("addStaple POSTs /staples with name", async () => {
    const f = mockFetch({ staples: [] });
    await addStaple("peanut butter");
    expect(f.mock.calls[0][0]).toContain("/staples");
    expect(JSON.parse((f.mock.calls[0][1]?.body as string) ?? "{}").name).toBe("peanut butter");
  });
  it("setStapleAutoAdd PATCHes", async () => {
    const f = mockFetch({ staples: [] });
    await setStapleAutoAdd(3, false);
    expect(f.mock.calls[0][1]?.method).toBe("PATCH");
    expect(f.mock.calls[0][0]).toContain("/staples/3");
  });
  it("addStapleToTrip POSTs /list/staples/{id}", async () => {
    const f = mockFetch({ staples: [] });
    await addStapleToTrip(3);
    expect(f.mock.calls[0][0]).toContain("/list/staples/3");
    expect(f.mock.calls[0][1]?.method).toBe("POST");
  });
  it("removeStapleFromTrip DELETEs /list/staples/{id}", async () => {
    const f = mockFetch({ staples: [] });
    await removeStapleFromTrip(3);
    expect(f.mock.calls[0][1]?.method).toBe("DELETE");
  });
  it("removeStaple DELETEs /staples/{id}", async () => {
    const f = mockFetch({ staples: [] });
    await removeStaple(3);
    expect(f.mock.calls[0][0]).toContain("/staples/3");
    expect(f.mock.calls[0][1]?.method).toBe("DELETE");
  });
});

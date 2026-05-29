import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
});

import { buildSessionStreamUrl, getSessionMessages } from "./api";

describe("session API", () => {
  it("builds stream URL with session id and cursor", () => {
    expect(buildSessionStreamUrl(42, 12)).toBe(
      "/api/sessions/42/stream?after=12",
    );
  });

  it("defaults after to 0", () => {
    expect(buildSessionStreamUrl(5)).toBe("/api/sessions/5/stream?after=0");
  });

  it("builds messages URL with session id and cursor", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await getSessionMessages(42, 5);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/sessions/42/messages?after=5",
      expect.any(Object),
    );
  });
});

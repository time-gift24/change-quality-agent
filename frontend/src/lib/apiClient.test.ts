import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, requestJson } from "./apiClient";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestJson", () => {
  it("uses same-origin credentials for cookie-backed API calls", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestJson("/api/auth/me")).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("returns undefined for no-content responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(null, {
          status: 204,
          statusText: "No Content",
        }),
      ),
    );

    await expect(requestJson<void>("/api/auth/logout")).resolves.toBeUndefined();
  });

  it("includes FastAPI error details in ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "SOP not found" }), {
          headers: { "Content-Type": "application/json" },
          status: 404,
          statusText: "Not Found",
        }),
      ),
    );

    await expect(requestJson("/api/sop/missing?env=dev")).rejects.toMatchObject({
      detail: "SOP not found",
      message: "API request failed: 404 Not Found: SOP not found",
      status: 404,
      statusText: "Not Found",
    } satisfies Partial<ApiError>);
  });
});

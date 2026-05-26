import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, requestJson } from "./apiClient";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestJson", () => {
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

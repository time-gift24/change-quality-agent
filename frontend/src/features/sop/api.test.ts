import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/apiClient";
import { getSopQualityCheckHistory } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SOP API", () => {
  it("includes FastAPI error details when loading check history fails", async () => {
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

    await expect(getSopQualityCheckHistory("missing", "dev")).rejects.toMatchObject({
      detail: "SOP not found",
      message: "API request failed: 404 Not Found: SOP not found",
      status: 404,
      statusText: "Not Found",
    } satisfies Partial<ApiError>);
  });
});

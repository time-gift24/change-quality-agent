import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildSopQualityCheckStreamUrl,
  startSopQualityCheck,
} from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("sop quality checks API", () => {
  it("maps a newly created check", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          check_id: "check-1",
          status: "pending",
          created: true,
          status_url: "/api/sop-quality-checks/check-1",
          stream_url: "/api/sop-quality-checks/check-1/stream",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(startSopQualityCheck("release-checklist", "dev")).resolves.toEqual({
      kind: "created",
      checkId: "check-1",
    });
  });

  it("maps an existing active check", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          check_id: "check-1",
          status: "running",
          created: false,
          status_url: "/api/sop-quality-checks/check-1",
          stream_url: "/api/sop-quality-checks/check-1/stream",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(startSopQualityCheck("release-checklist", "dev")).resolves.toEqual({
      kind: "active",
      checkId: "check-1",
    });
  });

  it("builds stream URLs with a sequence cursor", () => {
    expect(buildSopQualityCheckStreamUrl("check-1", 12)).toBe(
      "/api/sop-quality-checks/check-1/stream?after=12",
    );
  });
});

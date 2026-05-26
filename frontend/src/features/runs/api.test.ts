import { afterEach, describe, expect, it, vi } from "vitest";

import { buildRunEventsUrl, getRun } from "./api";
import type { RunSummary } from "./types";

describe("runs API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps SOP env details out of generic run summaries", () => {
    type HasEnvKey = "env_key" extends keyof RunSummary ? true : false;
    const hasEnvKey: HasEnvKey = false;

    const run: RunSummary = {
      run_id: "run-1",
      subject_type: "sop",
      subject_id: "payment-release",
      status: "running",
      current_node: "check_steps",
      completed_nodes: ["load_sop"],
      latest_sequence: 12,
    };

    expect(hasEnvKey).toBe(false);
    expect("env_key" in run).toBe(false);
  });

  it("builds replay event stream URLs with an after cursor", () => {
    expect(buildRunEventsUrl("run-1", 12)).toBe(
      "/api/runs/run-1/events?after=12",
    );
  });

  it("fetches run summaries from generic run endpoints", async () => {
    const summary: RunSummary = {
      run_id: "run-1",
      subject_type: "sop",
      subject_id: "payment-release",
      status: "success",
      current_node: null,
      completed_nodes: ["load_sop", "check_steps", "summarize_result"],
      latest_sequence: 18,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(summary));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getRun("run-1")).resolves.toEqual(summary);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1",
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    );
  });

});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

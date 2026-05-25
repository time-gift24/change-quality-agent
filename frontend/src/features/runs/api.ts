import { requestJson } from "../../lib/apiClient";
import type { RunEvent, RunSummary } from "./types";

export function getRun(runId: string): Promise<RunSummary> {
  return requestJson<RunSummary>(buildRunUrl(runId));
}

export function getRunEvents(
  runId: string,
  after?: number,
): Promise<RunEvent[]> {
  return requestJson<RunEvent[]>(buildRunEventsUrl(runId, after));
}

export function buildRunEventsUrl(runId: string, after?: number): string {
  const path = `${buildRunUrl(runId)}/events`;

  if (after === undefined) {
    return path;
  }

  return `${path}?after=${encodeURIComponent(String(after))}`;
}

function buildRunUrl(runId: string): string {
  return `/api/runs/${encodeURIComponent(runId)}`;
}

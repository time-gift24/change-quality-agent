import { ApiError, requestJson } from "../../lib/apiClient";
import type {
  SopEnvironment,
  SopPreview,
  SopRunHistoryItem,
  StartSopRunResult,
} from "./types";

type SopEnvironmentsResponse =
  | SopEnvironment[]
  | {
      environments: SopEnvironment[];
    };

type StartSopRunResponse = {
  run_id?: string;
  active_run_id?: string;
};

export async function getSopEnvironments(): Promise<SopEnvironment[]> {
  const response =
    await requestJson<SopEnvironmentsResponse>("/api/sop/environments");

  return Array.isArray(response) ? response : response.environments;
}

export function getSopPreview(
  sopId: string,
  envKey: string,
): Promise<SopPreview> {
  return requestJson<SopPreview>(buildSopUrl(sopId, envKey));
}

export async function startSopQualityRun(
  sopId: string,
  envKey: string,
): Promise<StartSopRunResult> {
  const response = await fetch(buildSopRunsUrl(sopId, envKey), {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
  const body = (await response.json()) as StartSopRunResponse;

  if (response.status === 202 && body.run_id) {
    return { kind: "started", runId: body.run_id };
  }

  if (response.status === 409 && body.active_run_id) {
    return { kind: "active", runId: body.active_run_id };
  }

  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }

  throw new Error("SOP run response did not include a run id.");
}

export async function getSopRunHistory(
  sopId: string,
  envKey: string,
): Promise<SopRunHistoryItem[]> {
  const response = await requestJson<{ runs: SopRunHistoryItem[] }>(
    buildSopRunsUrl(sopId, envKey),
  );

  return response.runs;
}

function buildSopUrl(sopId: string, envKey: string): string {
  return `/api/sop/${encodeURIComponent(sopId)}?env=${encodeURIComponent(
    envKey,
  )}`;
}

function buildSopRunsUrl(sopId: string, envKey: string): string {
  return `/api/sop/${encodeURIComponent(sopId)}/runs?env=${encodeURIComponent(
    envKey,
  )}`;
}

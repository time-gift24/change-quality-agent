import {
  ApiError,
  apiErrorFromResponse,
  requestJson,
} from "../../lib/apiClient";
import type {
  SopEnvironment,
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
  message?: string;
};

export async function getSopEnvironments(): Promise<SopEnvironment[]> {
  const response =
    await requestJson<SopEnvironmentsResponse>("/api/sop/environments");

  return Array.isArray(response) ? response : response.environments;
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

  if (response.status === 202) {
    const body = await readStartRunBody(response);

    if (!body.run_id) {
      throw new Error("SOP run response did not include a run id.");
    }

    return { kind: "started", runId: body.run_id };
  }

  if (response.status === 409) {
    const body = await readStartRunBody(response);

    if (!body.active_run_id) {
      throw new ApiError(response.status, response.statusText, body.message);
    }

    return { kind: "active", runId: body.active_run_id };
  }

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  throw new Error("SOP run response did not include a run id.");
}

async function readStartRunBody(response: Response): Promise<StartSopRunResponse> {
  try {
    return (await response.json()) as StartSopRunResponse;
  } catch {
    return {};
  }
}

export async function getSopRunHistory(
  sopId: string,
  envKey: string,
): Promise<SopRunHistoryItem[]> {
  return requestJson<SopRunHistoryItem[]>(buildSopRunsUrl(sopId, envKey));
}

export async function getRecentSopRuns(
  envKey: string,
  limit = 50,
): Promise<SopRunHistoryItem[]> {
  return requestJson<SopRunHistoryItem[]>(
    `/api/sop/recent/runs?env=${encodeURIComponent(envKey)}&limit=${limit}`,
  );
}

function buildSopRunsUrl(sopId: string, envKey: string): string {
  return `/api/sop/${encodeURIComponent(sopId)}/runs?env=${encodeURIComponent(
    envKey,
  )}`;
}

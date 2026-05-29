import { apiErrorFromResponse, requestJson } from "../../lib/apiClient";
import type {
  SopQualityCheckDetail,
  StartSopQualityCheckResult,
} from "./types";

type StartResponse = {
  check_id?: string;
  created?: boolean;
};

export async function startSopQualityCheck(
  sopId: string,
  envKey: string,
): Promise<StartSopQualityCheckResult> {
  const response = await fetch(
    `/api/sop-quality-checks?sop_id=${encodeURIComponent(
      sopId,
    )}&env=${encodeURIComponent(envKey)}`,
    { method: "POST", headers: { Accept: "application/json" } },
  );

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  const body = (await response.json()) as StartResponse;
  if (!body.check_id) {
    throw new Error("SOP quality check response did not include a check id.");
  }

  return {
    kind: body.created ? "created" : "active",
    checkId: body.check_id,
  };
}

export function getSopQualityCheck(
  checkId: string,
): Promise<SopQualityCheckDetail> {
  return requestJson<SopQualityCheckDetail>(
    `/api/sop-quality-checks/${encodeURIComponent(checkId)}`,
  );
}

export function buildSopQualityCheckStreamUrl(checkId: string, after = 0): string {
  return `/api/sop-quality-checks/${encodeURIComponent(checkId)}/stream?after=${after}`;
}

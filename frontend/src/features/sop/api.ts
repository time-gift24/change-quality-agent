import { requestJson } from "../../lib/apiClient";
import type { SopEnvironment, SopQualityCheckHistoryItem } from "./types";

type SopEnvironmentsResponse =
  | SopEnvironment[]
  | {
      environments: SopEnvironment[];
    };

export async function getSopEnvironments(): Promise<SopEnvironment[]> {
  const response =
    await requestJson<SopEnvironmentsResponse>("/api/sop/environments");

  return Array.isArray(response) ? response : response.environments;
}

export async function getSopQualityCheckHistory(
  sopId: string,
  envKey: string,
  limit = 20,
): Promise<SopQualityCheckHistoryItem[]> {
  return requestJson<SopQualityCheckHistoryItem[]>(
    `/api/sop-quality-checks?sop_id=${encodeURIComponent(
      sopId,
    )}&env=${encodeURIComponent(envKey)}&limit=${limit}`,
  );
}

export async function getRecentSopQualityChecks(
  envKey: string,
  limit = 50,
): Promise<SopQualityCheckHistoryItem[]> {
  return requestJson<SopQualityCheckHistoryItem[]>(
    `/api/sop-quality-checks?env=${encodeURIComponent(envKey)}&limit=${limit}`,
  );
}

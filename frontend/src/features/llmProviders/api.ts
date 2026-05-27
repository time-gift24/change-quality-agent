import { apiErrorFromResponse, requestJson } from "../../lib/apiClient";
import type {
  LlmProviderCreate,
  LlmProviderDetail,
  LlmProviderSummary,
  LlmProviderUpdate,
} from "./types";

const LLM_PROVIDERS_BASE = "/api/v1/llm-providers";

export function listLlmProviders(): Promise<LlmProviderSummary[]> {
  return requestJson<LlmProviderSummary[]>(LLM_PROVIDERS_BASE);
}

export function getLlmProvider(providerKey: string): Promise<LlmProviderDetail> {
  return requestJson<LlmProviderDetail>(buildProviderUrl(providerKey));
}

export function createLlmProvider(
  payload: LlmProviderCreate,
): Promise<LlmProviderDetail> {
  return requestJson<LlmProviderDetail>(LLM_PROVIDERS_BASE, {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export function updateLlmProvider(
  providerKey: string,
  payload: LlmProviderUpdate,
): Promise<LlmProviderDetail> {
  return requestJson<LlmProviderDetail>(buildProviderUrl(providerKey), {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "PATCH",
  });
}

export async function deleteLlmProvider(providerKey: string): Promise<void> {
  const headers = new Headers();
  headers.set("Accept", "application/json");

  const response = await fetch(buildProviderUrl(providerKey), {
    headers,
    method: "DELETE",
  });

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }
}

function buildProviderUrl(providerKey: string): string {
  return `${LLM_PROVIDERS_BASE}/${encodeURIComponent(providerKey)}`;
}

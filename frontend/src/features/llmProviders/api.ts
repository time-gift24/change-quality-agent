import { apiErrorFromResponse, requestJson } from "../../lib/apiClient";
import type {
  LlmProviderCreate,
  LlmProviderDetail,
  LlmProviderModelTestResponse,
  LlmProviderSummary,
  LlmProviderUpdate,
} from "./types";

const LLM_PROVIDERS_BASE = "/api/v1/llm-providers";

export function listLlmProviders(): Promise<LlmProviderSummary[]> {
  return requestJson<LlmProviderSummary[]>(LLM_PROVIDERS_BASE);
}

export function getLlmProvider(providerId: string): Promise<LlmProviderDetail> {
  return requestJson<LlmProviderDetail>(buildProviderUrl(providerId));
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
  providerId: string,
  payload: LlmProviderUpdate,
): Promise<LlmProviderDetail> {
  return requestJson<LlmProviderDetail>(buildProviderUrl(providerId), {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "PATCH",
  });
}

export async function deleteLlmProvider(providerId: string): Promise<void> {
  const headers = new Headers();
  headers.set("Accept", "application/json");

  const response = await fetch(buildProviderUrl(providerId), {
    headers,
    method: "DELETE",
  });

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }
}

export async function testLlmProviderModel(
  providerId: string,
  model: string,
): Promise<LlmProviderModelTestResponse> {
  const response = await fetch(`${buildProviderUrl(providerId)}/test`, {
    body: JSON.stringify({ model }),
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    method: "POST",
  });

  if (response.ok || response.status === 502) {
    return JSON.parse(await response.text()) as LlmProviderModelTestResponse;
  }

  throw await apiErrorFromResponse(response);
}

function buildProviderUrl(providerId: string): string {
  return `${LLM_PROVIDERS_BASE}/${encodeURIComponent(providerId)}`;
}

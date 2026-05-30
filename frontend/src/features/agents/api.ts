import { requestJson } from "../../lib/apiClient";
import type {
  AgentCapabilities,
  AgentCreate,
  AgentDetail,
  AgentDraftUpdate,
  AgentSessionStart,
  AgentSessionStartResponse,
  AgentSummary,
} from "./types";

const AGENTS_BASE = "/api/agents";

export function listAgents(): Promise<AgentSummary[]> {
  return requestJson<AgentSummary[]>(AGENTS_BASE);
}

export function getAgent(agentId: string): Promise<AgentDetail> {
  return requestJson<AgentDetail>(buildAgentUrl(agentId));
}

export function createAgent(payload: AgentCreate): Promise<AgentDetail> {
  return requestJson<AgentDetail>(AGENTS_BASE, {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export function updateAgentDraft(
  agentId: string,
  payload: AgentDraftUpdate,
): Promise<AgentDetail> {
  return requestJson<AgentDetail>(`${buildAgentUrl(agentId)}/draft`, {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "PATCH",
  });
}

export function getAgentCapabilities(): Promise<AgentCapabilities> {
  return requestJson<AgentCapabilities>(`${AGENTS_BASE}/capabilities`);
}

export function startAgentSession(
  agentId: string,
  payload: AgentSessionStart,
): Promise<AgentSessionStartResponse> {
  return requestJson<AgentSessionStartResponse>(
    `${buildAgentUrl(agentId)}/sessions`,
    {
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
    },
  );
}

function buildAgentUrl(agentId: string): string {
  return `${AGENTS_BASE}/${encodeURIComponent(agentId)}`;
}

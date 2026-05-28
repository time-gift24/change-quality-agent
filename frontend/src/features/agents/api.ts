import { requestJson } from "../../lib/apiClient";
import type {
  AgentCreate,
  AgentDetail,
  AgentDraftUpdate,
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

function buildAgentUrl(agentId: string): string {
  return `${AGENTS_BASE}/${encodeURIComponent(agentId)}`;
}

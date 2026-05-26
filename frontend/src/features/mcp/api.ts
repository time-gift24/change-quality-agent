import { apiErrorFromResponse, requestJson } from "../../lib/apiClient";
import type {
  McpLifecycleResponse,
  McpServerCreate,
  McpServerDetail,
  McpServerSummary,
  McpServerUpdate,
} from "./types";

const MCP_SERVERS_BASE = "/api/mcp/servers";

export function listMcpServers(): Promise<McpServerSummary[]> {
  return requestJson<McpServerSummary[]>(MCP_SERVERS_BASE);
}

export function getMcpServer(serverId: string): Promise<McpServerDetail> {
  return requestJson<McpServerDetail>(buildServerUrl(serverId));
}

export function createMcpServer(payload: McpServerCreate): Promise<McpServerDetail> {
  return requestJson<McpServerDetail>(MCP_SERVERS_BASE, {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export function updateMcpServer(
  serverId: string,
  payload: McpServerUpdate,
): Promise<McpServerDetail> {
  return requestJson<McpServerDetail>(buildServerUrl(serverId), {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "PATCH",
  });
}

export async function deleteMcpServer(serverId: string): Promise<void> {
  const headers = new Headers();
  headers.set("Accept", "application/json");

  const response = await fetch(buildServerUrl(serverId), {
    headers,
    method: "DELETE",
  });

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }
}

export function startMcpServer(serverId: string): Promise<McpLifecycleResponse> {
  return postLifecycle(serverId, "start");
}

export function stopMcpServer(serverId: string): Promise<McpLifecycleResponse> {
  return postLifecycle(serverId, "stop");
}

export function restartMcpServer(serverId: string): Promise<McpLifecycleResponse> {
  return postLifecycle(serverId, "restart");
}

export function checkMcpServer(serverId: string): Promise<McpLifecycleResponse> {
  return postLifecycle(serverId, "check");
}

function buildServerUrl(serverId: string): string {
  return `${MCP_SERVERS_BASE}/${encodeURIComponent(serverId)}`;
}

function postLifecycle(
  serverId: string,
  action: "start" | "stop" | "restart" | "check",
): Promise<McpLifecycleResponse> {
  return requestJson<McpLifecycleResponse>(`${buildServerUrl(serverId)}/${action}`, {
    method: "POST",
  });
}

import { apiErrorFromResponse, requestJson } from "../../lib/apiClient";
import type {
  McpLifecycleResponse,
  McpServerCreate,
  McpServerDetail,
  McpServerSummary,
  McpServerUpdate,
} from "./types";
import { getMcpAdminToken } from "./adminToken";

const MCP_SERVERS_BASE = "/api/mcp/servers";

export function listMcpServers(): Promise<McpServerSummary[]> {
  return requestJson<McpServerSummary[]>(MCP_SERVERS_BASE, withMcpAdminToken());
}

export function getMcpServer(serverId: string): Promise<McpServerDetail> {
  return requestJson<McpServerDetail>(buildServerUrl(serverId), withMcpAdminToken());
}

export function createMcpServer(payload: McpServerCreate): Promise<McpServerDetail> {
  return requestJson<McpServerDetail>(
    MCP_SERVERS_BASE,
    withMcpAdminToken({
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
    }),
  );
}

export function updateMcpServer(
  serverId: string,
  payload: McpServerUpdate,
): Promise<McpServerDetail> {
  return requestJson<McpServerDetail>(
    buildServerUrl(serverId),
    withMcpAdminToken({
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
      },
      method: "PATCH",
    }),
  );
}

export async function deleteMcpServer(serverId: string): Promise<void> {
  const init = withMcpAdminToken({ method: "DELETE" });
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  const response = await fetch(buildServerUrl(serverId), {
    ...init,
    headers,
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
  return requestJson<McpLifecycleResponse>(
    `${buildServerUrl(serverId)}/${action}`,
    withMcpAdminToken({
      method: "POST",
    }),
  );
}

type RequestInitWithHeaders = RequestInit & {
  headers?: HeadersInit;
};

function withMcpAdminToken(init: RequestInitWithHeaders = {}): RequestInit {
  const headers = new Headers(init.headers);
  const adminToken = getMcpAdminToken();

  if (adminToken) {
    headers.set("X-MCP-Admin-Token", adminToken);
  }

  return {
    ...init,
    headers,
  };
}

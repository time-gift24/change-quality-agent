// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/apiClient";
import {
  checkMcpServer,
  createMcpServer,
  deleteMcpServer,
  getMcpServer,
  listMcpServers,
  restartMcpServer,
  startMcpServer,
  stopMcpServer,
  updateMcpServer,
} from "./api";
import type { McpServerCreate, McpServerDetail, McpServerSummary } from "./types";

afterEach(() => {
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("MCP API", () => {
  it("calls list endpoint with GET", async () => {
    const servers: McpServerSummary[] = [];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(servers));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listMcpServers()).resolves.toEqual(servers);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/mcp/servers",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBeUndefined();
  });

  it("does not send legacy MCP admin token header from session storage", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("mcp-admin-token", "session-token-1");

    await listMcpServers();

    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
    expect(headers.get("X-MCP-Admin-Token")).toBeNull();
  });

  it("calls get endpoint with GET", async () => {
    const detail = buildDetail("server-1");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(detail));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getMcpServer("server-1")).resolves.toEqual(detail);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/mcp/servers/server-1",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBeUndefined();
  });

  it("calls create endpoint with POST", async () => {
    const payload: McpServerCreate = {
      name: "server-1",
      transport: "stdio",
      command: "uvx",
      args: ["mcp-server"],
      env: { API_KEY: "secret" },
      url: null,
      headers: {},
      enabled: true,
      desired_state: "running",
    };
    const detail = buildDetail("server-1");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(detail, 201, "Created"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createMcpServer(payload)).resolves.toEqual(detail);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/mcp/servers",
      expect.objectContaining({
        body: JSON.stringify(payload),
        method: "POST",
      }),
    );
  });

  it("calls update endpoint with PATCH", async () => {
    const detail = buildDetail("server-1");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(detail));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      updateMcpServer("server-1", { desired_state: "stopped" }),
    ).resolves.toEqual(detail);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/mcp/servers/server-1",
      expect.objectContaining({
        body: JSON.stringify({ desired_state: "stopped" }),
        method: "PATCH",
      }),
    );
  });

  it("calls delete endpoint with DELETE and accepts 204 no-content", async () => {
    const fetchMock = vi.fn().mockResolvedValue(noContentResponse());
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteMcpServer("server-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/mcp/servers/server-1",
      expect.objectContaining({
        headers: expect.any(Headers),
        method: "DELETE",
      }),
    );
  });

  it("throws ApiError with detail when delete fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          errorResponse(404, "Not Found", "MCP server not found."),
        ),
    );

    await expect(deleteMcpServer("missing")).rejects.toMatchObject({
      detail: "MCP server not found.",
      status: 404,
      statusText: "Not Found",
    } satisfies Partial<ApiError>);
  });

  it("calls lifecycle endpoints with POST", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(buildLifecycle("server-1")))
      .mockResolvedValueOnce(jsonResponse(buildLifecycle("server-1")))
      .mockResolvedValueOnce(jsonResponse(buildLifecycle("server-1")))
      .mockResolvedValueOnce(jsonResponse(buildLifecycle("server-1")))
      .mockResolvedValueOnce(jsonResponse(buildLifecycle("server-1")));
    vi.stubGlobal("fetch", fetchMock);

    await startMcpServer("server-1");
    await stopMcpServer("server-1");
    await restartMcpServer("server-1");
    await checkMcpServer("server-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/mcp/servers/server-1/start",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/mcp/servers/server-1/stop",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/mcp/servers/server-1/restart",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/mcp/servers/server-1/check",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("propagates 409/404/502 ApiError.detail values", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        errorResponse(409, "Conflict", "Stop the MCP server before updating its configuration."),
      )
      .mockResolvedValueOnce(
        errorResponse(404, "Not Found", "MCP server not found."),
      )
      .mockResolvedValueOnce(
        errorResponse(502, "Bad Gateway", "MCP lifecycle operation failed."),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      updateMcpServer("server-1", { name: "new-name" }),
    ).rejects.toMatchObject({
      detail: "Stop the MCP server before updating its configuration.",
      status: 409,
      statusText: "Conflict",
    } satisfies Partial<ApiError>);

    await expect(getMcpServer("missing")).rejects.toMatchObject({
      detail: "MCP server not found.",
      status: 404,
      statusText: "Not Found",
    } satisfies Partial<ApiError>);

    await expect(startMcpServer("server-1")).rejects.toMatchObject({
      detail: "MCP lifecycle operation failed.",
      status: 502,
      statusText: "Bad Gateway",
    } satisfies Partial<ApiError>);
  });
});

function buildDetail(id: string): McpServerDetail {
  return {
    args: ["mcp-server"],
    command: "uvx",
    desired_state: "running",
    enabled: true,
    env: { API_KEY: "********" },
    headers: {},
    id,
    last_checked_at: "2026-05-26T10:00:00Z",
    last_error: null,
    name: "server-1",
    runtime_status: "running",
    tool_count: 1,
    tools: [
      {
        description: "Tool description",
        discovered_at: "2026-05-26T10:00:00Z",
        input_schema: { type: "object" },
        name: "tool-1",
      },
    ],
    transport: "stdio",
    url: null,
  };
}

function buildLifecycle(serverId: string) {
  return {
    desired_state: "running",
    last_checked_at: "2026-05-26T10:00:00Z",
    last_error: null,
    runtime_status: "running",
    server_id: serverId,
    tool_count: 1,
  };
}

function jsonResponse(
  body: unknown,
  status = 200,
  statusText = "OK",
): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
    statusText,
  });
}

function errorResponse(
  status: number,
  statusText: string,
  detail: string,
): Response {
  return new Response(JSON.stringify({ detail }), {
    headers: { "Content-Type": "application/json" },
    status,
    statusText,
  });
}

function noContentResponse(): Response {
  return new Response(null, {
    status: 204,
    statusText: "No Content",
  });
}

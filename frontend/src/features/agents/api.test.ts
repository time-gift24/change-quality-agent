// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createAgent,
  getAgent,
  listAgents,
  updateAgentDraft,
} from "./api";
import type { AgentCreate, AgentDetail, AgentDraftUpdate } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("agent API", () => {
  it("calls list endpoint with GET", async () => {
    const agents: AgentDetail[] = [];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(agents));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listAgents()).resolves.toEqual(agents);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agents",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBeUndefined();
  });

  it("creates a CodeAgent-backed draft", async () => {
    const payload: AgentCreate = {
      description: "Checks release quality.",
      display_name: "Release Reviewer",
      draft: {
        mcp_server_ids: [],
        model: "codeagent:deepseek-v4-pro",
        model_config: {},
        provider_id: null,
        system_prompt: "You are careful.",
        tool_allowlist: [],
      },
    };
    const detail = buildAgent();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(detail, 201, "Created"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createAgent(payload)).resolves.toEqual(detail);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agents",
      expect.objectContaining({
        body: JSON.stringify(payload),
        method: "POST",
      }),
    );
  });

  it("gets and updates an agent draft with encoded id", async () => {
    const detail = buildAgent();
    const update: AgentDraftUpdate = {
      display_name: "Release Reviewer",
      enabled: true,
      draft: {
        mcp_server_ids: [],
        model: "gpt-5-mini",
        model_config: {},
        provider_id: "provider-1",
        system_prompt: "You are careful.",
        tool_allowlist: [],
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail));
    vi.stubGlobal("fetch", fetchMock);

    await getAgent("agent/1");
    await updateAgentDraft("agent/1", update);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/agents/agent%2F1",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/agents/agent%2F1/draft",
      expect.objectContaining({
        body: JSON.stringify(update),
        method: "PATCH",
      }),
    );
  });
});

function buildAgent(): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Checks release quality.",
    display_name: "Release Reviewer",
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "You are careful.",
      tool_allowlist: [],
    },
    enabled: true,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
  };
}

function jsonResponse(body: unknown, status = 200, statusText = "OK") {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
    statusText,
  });
}

// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAgent,
  getAgent,
  listAgents,
  updateAgentDraft,
} from "./api";
import { useAgentDetail, useAgentMutations, useAgents } from "./hooks";
import type { AgentCreate, AgentDetail, AgentSummary } from "./types";

vi.mock("./api", () => ({
  createAgent: vi.fn(),
  getAgent: vi.fn(),
  listAgents: vi.fn(),
  updateAgentDraft: vi.fn(),
}));

describe("agent hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads agent list on initial render", async () => {
    vi.mocked(listAgents).mockResolvedValueOnce([
      buildSummary({ id: "agent-1", display_name: "Agent 1" }),
    ]);

    const { result } = renderHook(() => useAgents());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current).toMatchObject({
      data: [buildSummary({ id: "agent-1", display_name: "Agent 1" })],
      error: null,
      loading: false,
    });
    expect(listAgents).toHaveBeenCalledTimes(1);
  });

  it("loads selected agent detail", async () => {
    vi.mocked(getAgent).mockResolvedValueOnce(
      buildDetail({ id: "agent-1", display_name: "Agent 1" }),
    );

    const { result } = renderHook(() => useAgentDetail("agent-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(getAgent).toHaveBeenCalledWith("agent-1");
    expect(result.current.data).toEqual(
      buildDetail({ id: "agent-1", display_name: "Agent 1" }),
    );
    expect(result.current.error).toBeNull();
  });

  it("skips detail loading without an agent id", () => {
    const { result } = renderHook(() => useAgentDetail(null));

    expect(getAgent).not.toHaveBeenCalled();
    expect(result.current).toMatchObject({
      data: null,
      error: null,
      loading: false,
    });
  });

  it("calls create and draft update mutations", async () => {
    const created = buildDetail({ id: "agent-1", display_name: "Agent 1" });
    const updated = buildDetail({ id: "agent-1", display_name: "Agent 1" });

    vi.mocked(createAgent).mockResolvedValueOnce(created);
    vi.mocked(updateAgentDraft).mockResolvedValueOnce(updated);

    const { result } = renderHook(() => useAgentMutations());
    const payload = buildCreatePayload();

    await act(async () => {
      await expect(result.current.createAgent(payload)).resolves.toEqual(created);
      await expect(
        result.current.updateAgentDraft("agent-1", {
          display_name: "Agent 1",
        }),
      ).resolves.toEqual(updated);
    });

    expect(createAgent).toHaveBeenCalledWith(payload);
    expect(updateAgentDraft).toHaveBeenCalledWith("agent-1", {
      display_name: "Agent 1",
    });
    expect(result.current.error).toBeNull();
    expect(result.current.pending).toBe(false);
  });
});

function buildSummary(overrides: Partial<AgentSummary> = {}): AgentSummary {
  return {
    created_at: "2026-01-01T00:00:00Z",
    description: null,
    display_name: "Default Agent",
    enabled: true,
    has_draft: true,
    id: "agent-default",
    latest_version: null,
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function buildDetail(overrides: Partial<AgentDetail> = {}): AgentDetail {
  return {
    ...buildSummary(overrides),
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "You are an agent.",
      tool_allowlist: [],
    },
    ...overrides,
  };
}

function buildCreatePayload(): AgentCreate {
  return {
    display_name: "Agent 1",
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "You are an agent.",
      tool_allowlist: [],
    },
  };
}

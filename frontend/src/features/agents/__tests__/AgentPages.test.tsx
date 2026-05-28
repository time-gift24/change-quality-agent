// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useAgentDetail, useAgentMutations, useAgents } from "../hooks";
import { AgentListPage } from "../pages/AgentListPage";
import type { AgentDetail } from "../types";
import { useLlmProviders } from "../../llmProviders/hooks";
import type { LlmProviderSummary } from "../../llmProviders/types";

vi.mock("../hooks", () => ({
  useAgentDetail: vi.fn(),
  useAgentMutations: vi.fn(),
  useAgents: vi.fn(),
}));

vi.mock("../../llmProviders/hooks", () => ({
  useLlmProviders: vi.fn(),
}));

const agent = buildAgent();
const provider = buildProvider();
const refetchAgents = vi.fn();
const refetchAgentDetail = vi.fn();
const refetchProviders = vi.fn();
const createAgent = vi.fn();
const updateAgentDraft = vi.fn();

beforeEach(() => {
  refetchAgents.mockReset();
  refetchAgentDetail.mockReset();
  refetchProviders.mockReset();
  createAgent.mockReset();
  updateAgentDraft.mockReset();

  vi.mocked(useAgents).mockReturnValue({
    data: [agent],
    error: null,
    loading: false,
    refetch: refetchAgents,
  });
  vi.mocked(useAgentDetail).mockReturnValue({
    data: agent,
    error: null,
    loading: false,
    refetch: refetchAgentDetail,
  });
  vi.mocked(useAgentMutations).mockReturnValue({
    createAgent,
    error: null,
    pending: false,
    updateAgentDraft,
  });
  vi.mocked(useLlmProviders).mockReturnValue({
    data: [provider],
    error: null,
    loading: false,
    refetch: refetchProviders,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Agent pages", () => {
  it("renders list rows, filters by search, and navigates to create", () => {
    render(
      <MemoryRouter initialEntries={["/agents"]}>
        <Routes>
          <Route element={<AgentListPage />} path="/agents" />
          <Route element={<div>新增 Agent 页面</div>} path="/agents/new" />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("main", { name: "Agent 配置主内容" })).toBeInTheDocument();
    expect(screen.getByText("Release Reviewer")).toBeInTheDocument();
    expect(screen.getByText("codeagent:deepseek-v4-pro")).toBeInTheDocument();
    expect(screen.getByLabelText("搜索 Agent")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索 Agent"), {
      target: { value: "missing" },
    });
    expect(screen.getByText("暂无 Agent。")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索 Agent"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "新增 Agent" }));

    expect(screen.getByText("新增 Agent 页面")).toBeInTheDocument();
  });
});

function buildAgent(): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Checks release quality before publishing.",
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
    latest_version: {
      id: "agent-version-1",
      model: "gpt-5-mini",
      provider_id: "provider-1",
      published_at: "2026-05-28T01:00:00Z",
      version_number: 1,
    },
    updated_at: "2026-05-28T02:00:00Z",
  };
}

function buildProvider(): LlmProviderSummary {
  return {
    api_key_configured: true,
    base_url: "https://api.openai.com/v1",
    created_at: "2026-05-27T00:00:00Z",
    default_headers: {},
    default_query: {},
    description: "Primary provider",
    display_name: "OpenAI Main",
    enabled: true,
    id: "provider-1",
    models: ["gpt-5-mini"],
    provider_type: "openai",
    updated_at: "2026-05-27T00:00:00Z",
  };
}

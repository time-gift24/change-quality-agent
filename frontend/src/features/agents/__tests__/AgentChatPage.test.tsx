// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useAgentChatMutations, useAgentDetail } from "../hooks";
import { useSessionStream } from "../../sessions/hooks";
import { AgentChatPage } from "../pages/AgentChatPage";
import type { AgentDetail } from "../types";
import {
  createInitialSessionViewState,
  type SessionViewState,
} from "../../sessions/reducer";
import type { SessionMessage } from "../../sessions/types";

vi.mock("../hooks", () => ({
  useAgentChatMutations: vi.fn(),
  useAgentDetail: vi.fn(),
}));

vi.mock("../../sessions/hooks", () => ({
  useSessionStream: vi.fn(),
}));

const startAgentSession = vi.fn();
const refetchAgentDetail = vi.fn();

beforeEach(() => {
  startAgentSession.mockReset();
  refetchAgentDetail.mockReset();
  vi.mocked(useAgentDetail).mockReturnValue({
    data: buildAgent(),
    error: null,
    loading: false,
    refetch: refetchAgentDetail,
  });
  vi.mocked(useAgentChatMutations).mockReturnValue({
    error: null,
    pending: false,
    startAgentSession,
  });
  vi.mocked(useSessionStream).mockReturnValue({
    error: null,
    loading: false,
    state: createInitialSessionViewState(),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AgentChatPage", () => {
  it("renders agent header and empty transcript state", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Existing Agent" })).toBeInTheDocument();
    expect(screen.getByText("尚未开始对话，输入消息试一下你的 Agent。")).toBeInTheDocument();
    expect(useSessionStream).toHaveBeenCalledWith(null);
  });

  it("starts a new session when sending the first message", async () => {
    startAgentSession.mockResolvedValueOnce({
      session_id: 42,
      stream_url: "/api/sessions/42/stream?after=0",
    });

    renderPage();

    fireEvent.change(screen.getByLabelText("对话消息"), {
      target: { value: "你好" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() =>
      expect(startAgentSession).toHaveBeenCalledWith("agent-1", {
        message: "你好",
        session_id: null,
      }),
    );
  });

  it("subscribes to the returned session id on next render", async () => {
    startAgentSession.mockResolvedValueOnce({
      session_id: 42,
      stream_url: "/api/sessions/42/stream?after=0",
    });

    renderPage();

    fireEvent.change(screen.getByLabelText("对话消息"), {
      target: { value: "你好" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(useSessionStream).toHaveBeenCalledWith(42));
  });

  it("renders assistant, user, and tool messages from session state", () => {
    const state: SessionViewState = {
      ...createInitialSessionViewState(),
      messages: [
        buildMessage({ content: "用户问题", role: "user", sequence: 1 }),
        buildMessage({ content: "助手回答", role: "assistant", sequence: 2 }),
        buildMessage({ content: "tool-result-payload", role: "tool", sequence: 3 }),
      ],
    };
    vi.mocked(useSessionStream).mockReturnValue({ error: null, loading: false, state });

    renderPage();

    expect(screen.getByText("用户问题")).toBeInTheDocument();
    expect(screen.getByText("助手回答")).toBeInTheDocument();
    expect(screen.getByText("tool-result-payload")).toBeInTheDocument();
  });

  it("disables the send button while pending or while a connection is open", () => {
    vi.mocked(useAgentChatMutations).mockReturnValue({
      error: null,
      pending: true,
      startAgentSession,
    });

    renderPage();

    expect(screen.getByRole("button", { name: "发送中..." })).toBeDisabled();
  });

  it("disables send when the connection is open and not yet completed", () => {
    const state: SessionViewState = {
      ...createInitialSessionViewState(),
      connectionStatus: "open",
    };
    vi.mocked(useSessionStream).mockReturnValue({ error: null, loading: false, state });

    renderPage();

    fireEvent.change(screen.getByLabelText("对话消息"), {
      target: { value: "再问一句" },
    });
    expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  });
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/agents/agent-1/chat"]}>
      <Routes>
        <Route element={<AgentChatPage />} path="/agents/:agentId/chat" />
      </Routes>
    </MemoryRouter>,
  );
}

function buildAgent(overrides: Partial<AgentDetail> = {}): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Existing description",
    display_name: "Existing Agent",
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "你是一个 Agent。",
      tool_allowlist: [],
    },
    enabled: true,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
    ...overrides,
  };
}

function buildMessage(overrides: Partial<SessionMessage>): SessionMessage {
  return {
    additional_kwargs: {},
    content: "",
    created_at: "2026-05-28T00:00:00Z",
    id: `msg-${overrides.sequence ?? 0}`,
    role: "assistant",
    sequence: 0,
    session_id: 42,
    ...overrides,
  };
}

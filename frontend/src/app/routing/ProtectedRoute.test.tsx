// @vitest-environment jsdom

import { type ReactNode } from "react";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "../../features/auth/AuthContext";
import type { CurrentUser } from "../../features/auth/types";
import { App } from "../App";

vi.mock("../../features/sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP Page</div>,
}));

vi.mock("../../features/sop/hooks", () => ({
  useRecentSopQualityChecks: () => ({
    data: [],
    error: null,
    loading: false,
  }),
  useSopEnvironments: () => ({
    data: [],
    error: null,
    loading: false,
  }),
}));

vi.mock("../../features/mcp/pages/McpListPage", () => ({
  McpListPage: () => (
    <div role="region" aria-label="MCP 管理 mock">
      <h1>MCP 管理</h1>
    </div>
  ),
}));

vi.mock("../../features/mcp/pages/McpDetailPage", () => ({
  McpDetailPage: () => (
    <div role="region" aria-label="MCP 详情 mock">
      <h1>MCP 详情</h1>
    </div>
  ),
}));

vi.mock("../../features/mcp/pages/McpServerFormPage", () => ({
  McpCreatePage: () => <div>新增 MCP Server</div>,
  McpEditPage: () => <div>编辑 MCP Server</div>,
}));

vi.mock("../../features/agents/pages/AgentListPage", () => ({
  AgentListPage: () => (
    <div role="region" aria-label="Agent 配置 mock">
      <h1>Agent 配置</h1>
    </div>
  ),
}));

vi.mock("../../features/agents/pages/AgentFormPage", () => ({
  AgentCreatePage: () => <div>新增 Agent 页面</div>,
  AgentEditPage: () => <div>编辑 Agent 页面</div>,
}));

vi.mock("../../features/auth/AuthContext", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: vi.fn(),
}));

describe("ProtectedRoute", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("blocks non-admin route access", () => {
    vi.mocked(useAuth).mockReturnValue(buildAuthValue(buildUser({ is_admin: false })));
    window.history.pushState({}, "", "/mcp");

    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: "403 Forbidden",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("需要管理权限才能访问该功能。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回 SOP" })).toHaveAttribute("href", "/sop");
  });

  it("allows admin route access", () => {
    vi.mocked(useAuth).mockReturnValue(buildAuthValue(buildUser({ is_admin: true })));
    window.history.pushState({}, "", "/mcp");

    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: "MCP 管理",
      }),
    ).toBeInTheDocument();
  });

  it("blocks non-admin access to /agents", () => {
    vi.mocked(useAuth).mockReturnValue(buildAuthValue(buildUser({ is_admin: false })));
    window.history.pushState({}, "", "/agents");

    render(<App />);

    expect(
      screen.getByRole("heading", { name: "403 Forbidden" }),
    ).toBeInTheDocument();
  });

  it("allows admin access to /agents", () => {
    vi.mocked(useAuth).mockReturnValue(buildAuthValue(buildUser({ is_admin: true })));
    window.history.pushState({}, "", "/agents");

    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Agent 配置" }),
    ).toBeInTheDocument();
  });
});

function buildAuthValue(user: CurrentUser) {
  return {
    loginAs: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
    status: "authenticated" as const,
    user,
  };
}

function buildUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    account: "common",
    id: "user-common",
    is_admin: false,
    meta: {},
    ...overrides,
  };
}

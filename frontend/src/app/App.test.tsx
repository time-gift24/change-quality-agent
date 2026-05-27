// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser } from "../features/auth/api";
import type { CurrentUser } from "../features/auth/types";
import { ApiError } from "../lib/apiClient";
import { App } from "./App";

vi.mock("../features/sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP 质检</div>,
}));

vi.mock("../features/auth/api", () => ({
  devLogin: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("../features/sop/hooks", () => ({
  useRecentSopRuns: () => ({
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

vi.mock("../features/mcp/pages/McpListPage", () => ({
  McpListPage: () => (
    <div role="region" aria-label="MCP 管理 mock">
      <h1>MCP 管理</h1>
    </div>
  ),
}));

vi.mock("../features/mcp/pages/McpDetailPage", () => ({
  McpDetailPage: () => (
    <div role="region" aria-label="MCP 详情 mock">
      <h1>MCP 详情</h1>
    </div>
  ),
}));

describe("App", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getCurrentUser).mockResolvedValue(buildUser());
  });

  it("renders sop route by default", async () => {
    window.history.pushState({}, "", "/");

    render(<App />);

    expect(await screen.findByText("SOP 质检")).toBeInTheDocument();
  });

  it("shows dev user picker when auth bootstrap is anonymous", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiError(401, "Unauthorized", "Authentication required."),
    );

    render(<App />);

    expect(await screen.findByRole("button", { name: /common/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /admin/i })).toBeInTheDocument();
  });
});

function buildUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    account: "common",
    id: "user-common",
    is_admin: false,
    meta: {},
    ...overrides,
  };
}

// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { devLogin, getCurrentUser } from "../features/auth/api";
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
    vi.mocked(devLogin).mockResolvedValue(buildUser());
  });

  it("renders sop route by default", async () => {
    window.history.pushState({}, "", "/");

    render(<App />);

    expect(await screen.findByText("SOP 质检")).toBeInTheDocument();
  });

  it("hides MCP navigation for a common user", async () => {
    window.history.pushState({}, "", "/sop");
    vi.mocked(getCurrentUser).mockResolvedValue(buildUser({ is_admin: false }));

    render(<App />);

    expect(await screen.findByText("SOP 质检")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "MCP 管理" }),
    ).not.toBeInTheDocument();
  });

  it("shows MCP navigation for an admin user", async () => {
    window.history.pushState({}, "", "/sop");
    vi.mocked(getCurrentUser).mockResolvedValue(buildUser({ is_admin: true }));

    render(<App />);

    expect(await screen.findByText("SOP 质检")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "MCP 管理" })).toBeInTheDocument();
  });

  it("shows a dev user switcher after entering the workspace", async () => {
    window.history.pushState({}, "", "/sop");
    vi.mocked(getCurrentUser).mockResolvedValue(
      buildUser({ account: "common", is_admin: false }),
    );

    render(<App />);

    expect(await screen.findByText("SOP 质检")).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: "开发用户" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Common" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Admin" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("switches the workspace user in dev mode", async () => {
    window.history.pushState({}, "", "/sop");
    vi.mocked(getCurrentUser).mockResolvedValue(
      buildUser({ account: "common", is_admin: false }),
    );
    vi.mocked(devLogin).mockResolvedValue(
      buildUser({ account: "admin", id: "user-admin", is_admin: true }),
    );

    render(<App />);

    expect(await screen.findByText("SOP 质检")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "MCP 管理" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Admin" }));

    expect(devLogin).toHaveBeenCalledWith("admin");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "MCP 管理" })).toBeInTheDocument();
    });
  });

  it("shows dev user picker when auth bootstrap is anonymous", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiError(401, "Unauthorized", "Authentication required."),
    );

    render(<App />);

    expect(await screen.findByRole("button", { name: /common/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /admin/i })).toBeInTheDocument();
  });

  it("submits common dev login and disables choices while pending", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiError(401, "Unauthorized", "Authentication required."),
    );
    const loginComplete = createDeferred<CurrentUser>();
    vi.mocked(devLogin).mockReturnValue(loginComplete.promise);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Common" }));

    expect(devLogin).toHaveBeenCalledWith("common");
    expect(screen.getByRole("button", { name: /signing in…/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Admin" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");

    loginComplete.resolve(buildUser());
    await waitFor(() => {
      expect(screen.getByText("SOP 质检")).toBeInTheDocument();
    });
  });

  it("shows dev login API error and re-enables choices", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiError(401, "Unauthorized", "Authentication required."),
    );
    vi.mocked(devLogin).mockRejectedValue(
      new ApiError(500, "Internal Server Error", "Unable to switch to the requested account."),
    );

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Admin" }));

    expect(devLogin).toHaveBeenCalledWith("admin");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to switch to the requested account.",
    );
    expect(screen.getByRole("alert")).toHaveClass("break-words");
    expect(screen.getByRole("button", { name: "Common" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Admin" })).toBeEnabled();
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

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });

  return { promise, resolve };
}

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

    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();
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

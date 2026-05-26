// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { useAuthz } from "./useAuthz";

vi.mock("../../features/sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP Page</div>,
}));

vi.mock("./useAuthz", () => ({
  useAuthz: vi.fn(),
}));

describe("ProtectedRoute", () => {
  it("blocks non-admin route access", () => {
    vi.mocked(useAuthz).mockReturnValue({ isAdmin: false });
    window.history.pushState({}, "", "/mcp");

    render(<App />);

    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();
  });

  it("allows admin route access", () => {
    vi.mocked(useAuthz).mockReturnValue({ isAdmin: true });
    window.history.pushState({}, "", "/mcp");

    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: "MCP 管理",
      }),
    ).toBeInTheDocument();
  });
});

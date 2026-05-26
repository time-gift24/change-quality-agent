// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("../features/sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP 质检</div>,
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
  it("renders sop route by default", async () => {
    window.history.pushState({}, "", "/");

    render(<App />);

    expect(await screen.findByText(/质量检查|SOP/i)).toBeInTheDocument();
  });
});

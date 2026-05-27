// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import type { McpServerDetail as McpServerDetailType } from "../types";
import { McpDetailPage } from "./McpDetailPage";

function renderDetailPage(
  route = "/mcp/srv-1",
  state?: Record<string, unknown>,
) {
  return render(
    <MemoryRouter initialEntries={[state ? { pathname: route, state } : route]}>
      <Routes>
        <Route element={<McpDetailPage />} path="/mcp/:serverId">
          <Route element={null} path="edit" />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

vi.mock("../hooks", () => ({
  useMcpMutations: vi.fn(),
  useMcpServerDetail: vi.fn(),
  useMcpServers: vi.fn(),
}));

const detail: McpServerDetailType = {
  args: ["--alpha"],
  command: "echo",
  desired_state: "running",
  enabled: true,
  env: { API_KEY: "********" },
  headers: { Authorization: "********" },
  id: "srv-1",
  last_checked_at: null,
  last_error: null,
  name: "Alpha Server",
  runtime_status: "running",
  tool_count: 1,
  tools: [
    {
      name: "alpha.search",
      description: "Search alpha docs",
      discovered_at: null,
      input_schema: { type: "object" },
    },
  ],
  transport: "stdio",
  url: null,
};

const updateServer = vi.fn();
const deleteServer = vi.fn();
const startServer = vi.fn();
const stopServer = vi.fn();
const restartServer = vi.fn();
const checkServer = vi.fn();
const refetchServers = vi.fn();
const refetchDetail = vi.fn();

beforeEach(() => {
  updateServer.mockReset();
  deleteServer.mockReset();
  startServer.mockReset();
  stopServer.mockReset();
  restartServer.mockReset();
  checkServer.mockReset();
  refetchServers.mockReset();
  refetchDetail.mockReset();
  window.sessionStorage.clear();

  vi.mocked(useMcpServers).mockReturnValue({
    data: [],
    error: null,
    loading: false,
    refetch: refetchServers,
  });

  vi.mocked(useMcpServerDetail).mockReturnValue({
    data: detail,
    error: null,
    loading: false,
    refetch: refetchDetail,
  });

  vi.mocked(useMcpMutations).mockReturnValue({
    checkServer,
    createServer: vi.fn(),
    deleteServer,
    error: null,
    pending: false,
    restartServer,
    startServer,
    stopServer,
    updateServer,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("McpDetailPage", () => {
  it("renders breadcrumb with server name", () => {
    renderDetailPage();

    const nav = screen.getByRole("navigation", { name: "面包屑" });
    expect(within(nav).getByRole("link", { name: "MCP 管理" })).toHaveAttribute("href", "/mcp");
    expect(within(nav).getByRole("link", { name: "Alpha Server" })).toHaveAttribute("href", "/mcp/srv-1");
    expect(within(nav).getByText("查看")).toHaveAttribute("aria-current", "page");
  });

  it("renders H1 with server name", () => {
    renderDetailPage();
    expect(screen.getByRole("heading", { name: "Alpha Server" })).toBeInTheDocument();
  });

  it("shows tools snapshot below the read-only form", () => {
    renderDetailPage();

    expect(screen.getByRole("textbox", { name: /服务名称/ })).toHaveValue("Alpha Server");
    expect(screen.getByRole("textbox", { name: /服务名称/ })).toHaveAttribute("readonly");
    expect(screen.getByText("alpha.search")).toBeInTheDocument();
  });

  it("renders loading skeleton on cold load", () => {
    vi.mocked(useMcpServerDetail).mockReturnValue({
      data: null,
      error: null,
      loading: true,
      refetch: vi.fn(),
    });

    renderDetailPage();

    expect(screen.getByText("加载详情中…")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "srv-1" })).toBeInTheDocument();
  });

  it("shows 404 card without auto-redirect", () => {
    const notFoundErr = new Error("Not Found") as Error & { status: number };
    notFoundErr.status = 404;

    vi.mocked(useMcpServerDetail).mockReturnValue({
      data: null,
      error: notFoundErr,
      loading: false,
      refetch: refetchDetail,
    });

    renderDetailPage();

    expect(screen.getByText("MCP 服务不存在")).toBeInTheDocument();
    expect(screen.getByText("返回列表")).toBeInTheDocument();

    expect(refetchDetail).not.toHaveBeenCalled();
  });

  it("shows server configuration as a read-only form by default", () => {
    renderDetailPage();

    expect(screen.getByRole("region", { name: "配置工作区" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "配置总览" })).toBeInTheDocument();
    expect(screen.queryByText("READ ONLY")).not.toBeInTheDocument();
    expect(screen.getByLabelText("传输方式")).toBeDisabled();
    expect(screen.getByRole("textbox", { name: /command/ })).toHaveValue("echo");
  });

  it("shows success notice from navigation state", () => {
    renderDetailPage("/mcp/srv-1", { mcpNotice: "MCP Server 配置已保存。" });

    expect(screen.getByRole("status")).toHaveTextContent("MCP Server 配置已保存。");
  });

  it("shows status badge and transport in subtitle", () => {
    renderDetailPage();

    expect(screen.getAllByText("running").length).toBeGreaterThan(0);
    expect(screen.getAllByText("stdio").length).toBeGreaterThan(0);
  });

  it("shows mutation error alert", () => {
    vi.mocked(useMcpMutations).mockReturnValue({
      checkServer,
      createServer: vi.fn(),
      deleteServer,
      error: new Error("something went wrong"),
      pending: false,
      restartServer,
      startServer,
      stopServer,
      updateServer,
    });

    renderDetailPage();

    expect(screen.getByRole("alert")).toHaveTextContent("something went wrong");
  });

  it("shows env and headers in config panel", () => {
    renderDetailPage();

    expect(screen.getByRole("textbox", { name: /env/ })).toHaveValue("API_KEY=********");
    expect(screen.getByRole("textbox", { name: /headers/ })).toHaveValue("Authorization=********");
  });
});

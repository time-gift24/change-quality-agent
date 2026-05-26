// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useMcpMutations, useMcpServers } from "../hooks";
import type { McpServerSummary } from "../types";
import { McpListPage } from "./McpListPage";

function renderListPage() {
  return render(
    <MemoryRouter initialEntries={["/mcp"]}>
      <Routes>
        <Route element={<McpListPage />} path="/mcp" />
        <Route element={<div>新增 MCP Server 页面</div>} path="/mcp/new" />
      </Routes>
    </MemoryRouter>,
  );
}

vi.mock("../hooks", () => ({
  useMcpMutations: vi.fn(),
  useMcpServerDetail: vi.fn(),
  useMcpServers: vi.fn(),
}));

const createServer = vi.fn();
const deleteServer = vi.fn();
const startServer = vi.fn();
const stopServer = vi.fn();
const restartServer = vi.fn();
const checkServer = vi.fn();
const refetchServers = vi.fn();

const servers: McpServerSummary[] = [
  buildSummary({ id: "srv-1", name: "Alpha Server", tool_count: 1 }),
  buildSummary({
    id: "srv-2",
    name: "Beta Server",
    runtime_status: "stopped",
    tool_count: 2,
  }),
];

beforeEach(() => {
  createServer.mockReset();
  deleteServer.mockReset();
  startServer.mockReset();
  stopServer.mockReset();
  restartServer.mockReset();
  checkServer.mockReset();
  refetchServers.mockReset();
  window.sessionStorage.clear();
  vi.mocked(useMcpServers).mockReturnValue({
    data: servers,
    error: null,
    loading: false,
    refetch: refetchServers,
  });

  vi.mocked(useMcpMutations).mockReturnValue({
    checkServer,
    createServer,
    deleteServer,
    error: null,
    pending: false,
    restartServer,
    startServer,
    stopServer,
    updateServer: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("McpListPage", () => {
  it("renders MCP main content without owning the workspace sidebar", () => {
    renderListPage();

    expect(screen.getByRole("main", { name: "MCP 管理主内容" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "工作台侧边栏" })).not.toBeInTheDocument();
  });

  it("keeps the table visible in the page scroll area", () => {
    renderListPage();

    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("renders server names as links in table rows", () => {
    renderListPage();

    const link = screen.getByRole("link", { name: /Alpha Server/ });
    expect(link).toHaveAttribute("href", "/mcp/srv-1");

    expect(screen.getByRole("link", { name: /Beta Server/ })).toHaveAttribute("href", "/mcp/srv-2");
  });

  it("renders server list in the table", () => {
    renderListPage();

    const rows = screen.getAllByRole("row");
    // header row + 2 data rows
    expect(rows.length).toBe(3);

    expect(screen.getByText("Alpha Server")).toBeInTheDocument();
    expect(screen.getByText("Beta Server")).toBeInTheDocument();
  });

  it("navigates to the create page when clicking 新增 Server", () => {
    renderListPage();

    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    expect(screen.getByText("新增 MCP Server 页面")).toBeInTheDocument();
  });

  it("filters servers by search text", () => {
    renderListPage();

    fireEvent.change(screen.getByRole("searchbox", { name: "搜索 MCP 服务" }), {
      target: { value: "Alpha" },
    });

    expect(screen.getByText("Alpha Server")).toBeInTheDocument();
    expect(screen.queryByText("Beta Server")).not.toBeInTheDocument();
  });

  it("invokes start stop restart check actions via dropdown", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderListPage();

    // Open dropdown for Alpha Server (running)
    const triggers = screen.getAllByRole("button", { name: "更多操作" });
    fireEvent.click(triggers[0]);

    // Should show 停止 (running), not 启动
    expect(screen.getByRole("menuitem", { name: "停止" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "启动" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("menuitem", { name: "停止" }));
    expect(stopServer).toHaveBeenCalledWith("srv-1");

    // Reopen for restart
    fireEvent.click(triggers[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "重启" }));
    expect(restartServer).toHaveBeenCalledWith("srv-1");

    // Check
    fireEvent.click(triggers[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "检查" }));
    expect(checkServer).toHaveBeenCalledWith("srv-1");
  });

  it("shows 启动 for stopped server", () => {
    renderListPage();

    const triggers = screen.getAllByRole("button", { name: "更多操作" });
    // Beta Server is stopped
    fireEvent.click(triggers[1]);

    expect(screen.getByRole("menuitem", { name: "启动" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "停止" })).not.toBeInTheDocument();
  });

  it("shows mutation error in alert", () => {
    vi.mocked(useMcpMutations).mockReturnValue({
      checkServer,
      createServer,
      deleteServer,
      error: new Error("server is running"),
      pending: false,
      restartServer,
      startServer,
      stopServer,
      updateServer: vi.fn(),
    });

    renderListPage();

    expect(screen.getByRole("alert")).toHaveTextContent("server is running");
  });

  it("asks for confirmation before delete and restart via dropdown", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    renderListPage();

    const triggers = screen.getAllByRole("button", { name: "更多操作" });

    // Alpha Server (running) — restart needs confirm
    fireEvent.click(triggers[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "重启" }));
    expect(confirmSpy).toHaveBeenCalledWith("确认重启 Alpha Server？");

    // Beta Server — delete needs confirm
    fireEvent.click(triggers[1]);
    fireEvent.click(screen.getByRole("menuitem", { name: "删除" }));
    expect(confirmSpy).toHaveBeenCalledWith("确认删除 Beta Server？");
  });

  it("stores the MCP admin token and refetches servers", async () => {
    renderListPage();

    fireEvent.change(screen.getByLabelText("MCP Admin Token"), {
      target: { value: "token-from-ui" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Token" }));

    await waitFor(() => expect(refetchServers).toHaveBeenCalledTimes(1));
    expect(window.sessionStorage.getItem("mcp-admin-token")).toBe("token-from-ui");
  });

  it("shows status badge for running and stopped servers", () => {
    renderListPage();

    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("stopped")).toBeInTheDocument();
  });

  it("shows footer with server count", () => {
    renderListPage();

    expect(screen.getByText("共 2 个服务")).toBeInTheDocument();
  });
});

function buildSummary(overrides: Partial<McpServerSummary> = {}): McpServerSummary {
  return {
    args: [],
    command: "echo",
    desired_state: "running",
    enabled: true,
    env: {},
    headers: {},
    id: "srv-default",
    last_checked_at: null,
    last_error: null,
    name: "Default Server",
    runtime_status: "running",
    tool_count: 0,
    transport: "stdio",
    url: null,
    ...overrides,
  };
}

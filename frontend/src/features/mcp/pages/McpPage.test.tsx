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

import { App } from "../../../app/App";
import { useAuthz } from "../../../app/routing/useAuthz";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import type { McpServerDetail, McpServerSummary } from "../types";
import { McpPage } from "./McpPage";

vi.mock("../../../app/routing/useAuthz", () => ({
  useAuthz: vi.fn(),
}));

vi.mock("../../sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP Mock</div>,
}));

vi.mock("../hooks", () => ({
  useMcpMutations: vi.fn(),
  useMcpServerDetail: vi.fn(),
  useMcpServers: vi.fn(),
}));

const createServer = vi.fn();
const updateServer = vi.fn();
const deleteServer = vi.fn();
const startServer = vi.fn();
const stopServer = vi.fn();
const restartServer = vi.fn();
const checkServer = vi.fn();

const servers: McpServerSummary[] = [
  buildSummary({ id: "srv-1", name: "Alpha Server", tool_count: 1 }),
  buildSummary({
    id: "srv-2",
    name: "Beta Server",
    runtime_status: "stopped",
    tool_count: 2,
  }),
];

const detailById: Record<string, McpServerDetail> = {
  "srv-1": buildDetail({
    id: "srv-1",
    name: "Alpha Server",
    tools: [
      {
        name: "alpha.search",
        description: "Search alpha docs",
        discovered_at: null,
        input_schema: { type: "object" },
      },
    ],
    tool_count: 1,
  }),
  "srv-2": buildDetail({
    id: "srv-2",
    name: "Beta Server",
    runtime_status: "stopped",
    tools: [
      {
        name: "beta.lookup",
        description: "Lookup beta index",
        discovered_at: null,
        input_schema: { type: "object" },
      },
      {
        name: "beta.diff",
        description: "Diff beta snapshots",
        discovered_at: null,
        input_schema: { type: "object" },
      },
    ],
    tool_count: 2,
  }),
};

beforeEach(() => {
  createServer.mockReset();
  updateServer.mockReset();
  deleteServer.mockReset();
  startServer.mockReset();
  stopServer.mockReset();
  restartServer.mockReset();
  checkServer.mockReset();
  vi.mocked(useAuthz).mockReturnValue({ isAdmin: true });

  vi.mocked(useMcpServers).mockReturnValue({
    data: servers,
    error: null,
    loading: false,
    refetch: vi.fn(),
  });

  vi.mocked(useMcpServerDetail).mockImplementation((serverId) => ({
    data: serverId ? detailById[serverId] ?? null : null,
    error: null,
    loading: false,
    refetch: vi.fn(),
  }));

  vi.mocked(useMcpMutations).mockReturnValue({
    checkServer,
    createServer,
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
});

describe("McpPage", () => {
  it("renders mcp workspace through /mcp route", () => {
    window.history.pushState({}, "", "/mcp");
    render(<App />);

    expect(screen.getByRole("heading", { name: "MCP 管理" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "MCP 服务列表" })).toBeInTheDocument();
  });

  it("renders server list in left panel", () => {
    render(<McpPage />);

    const list = screen.getByRole("list", { name: "MCP 服务列表" });

    expect(within(list).getByText("Alpha Server")).toBeInTheDocument();
    expect(within(list).getByText("Beta Server")).toBeInTheDocument();
  });

  it("switches right detail when clicking list item", () => {
    render(<McpPage />);

    const detail = screen.getByRole("region", { name: "MCP 服务详情" });
    expect(within(detail).getByRole("heading", { name: "Alpha Server" }))
      .toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "选择服务 Beta Server" }));

    expect(within(detail).getByRole("heading", { name: "Beta Server" }))
      .toBeInTheDocument();
  });

  it("shows tools after switching to tools snapshot tab", () => {
    render(<McpPage />);

    fireEvent.click(screen.getByRole("button", { name: "选择服务 Beta Server" }));
    fireEvent.click(screen.getByRole("tab", { name: "工具快照" }));

    const toolsList = screen.getByRole("list", { name: "工具快照列表" });
    expect(within(toolsList).getByText("beta.lookup")).toBeInTheDocument();
    expect(within(toolsList).getByText("beta.diff")).toBeInTheDocument();
  });

  it("invokes start stop restart check actions", () => {
    render(<McpPage />);

    fireEvent.click(screen.getByRole("button", { name: "启动 Alpha Server" }));
    fireEvent.click(screen.getByRole("button", { name: "停止 Alpha Server" }));
    fireEvent.click(screen.getByRole("button", { name: "重启 Alpha Server" }));
    fireEvent.click(screen.getByRole("button", { name: "检查 Alpha Server" }));

    expect(startServer).toHaveBeenCalledWith("srv-1");
    expect(stopServer).toHaveBeenCalledWith("srv-1");
    expect(restartServer).toHaveBeenCalledWith("srv-1");
    expect(checkServer).toHaveBeenCalledWith("srv-1");
  });

  it("validates required command for stdio and closes drawer on Escape", () => {
    render(<McpPage />);
    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    const nameInput = within(dialog).getByLabelText("服务名称");

    expect(nameInput).toHaveFocus();
    fireEvent.change(nameInput, { target: { value: "Gamma Server" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "stdio 模式需要填写 command。",
    );
    expect(createServer).not.toHaveBeenCalled();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(
      screen.queryByRole("dialog", { name: "新增 MCP 服务" }),
    ).not.toBeInTheDocument();
  });

  it("validates required url for http before submit", () => {
    render(<McpPage />);
    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    fireEvent.change(within(dialog).getByLabelText("服务名称"), {
      target: { value: "Delta Server" },
    });
    fireEvent.change(within(dialog).getByLabelText("传输方式"), {
      target: { value: "http" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "http 模式需要填写 url。",
    );
    expect(createServer).not.toHaveBeenCalled();
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

function buildDetail(overrides: Partial<McpServerDetail> = {}): McpServerDetail {
  return {
    ...buildSummary(overrides),
    tools: [],
    ...overrides,
  };
}

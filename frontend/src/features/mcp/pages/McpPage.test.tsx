// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { App } from "../../../app/App";
import { useAuthz } from "../../../app/routing/useAuthz";
import { ApiError } from "../../../lib/apiClient";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import { McpServerDetail } from "../components/McpServerDetail";
import type {
  McpServerDetail as McpServerDetailType,
  McpServerSummary,
} from "../types";
import { McpPage } from "./McpPage";

function renderMcpPage() {
  return render(
    <MemoryRouter initialEntries={["/mcp"]}>
      <McpPage />
    </MemoryRouter>,
  );
}

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
const refetchServers = vi.fn();
const refetchDetail = vi.fn();

const servers: McpServerSummary[] = [
  buildSummary({ id: "srv-1", name: "Alpha Server", tool_count: 1 }),
  buildSummary({
    id: "srv-2",
    name: "Beta Server",
    runtime_status: "stopped",
    tool_count: 2,
  }),
];

const detailById: Record<string, McpServerDetailType> = {
  "srv-1": buildDetail({
    args: ["--alpha"],
    id: "srv-1",
    env: { API_KEY: "********" },
    headers: { Authorization: "********" },
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
  refetchServers.mockReset();
  refetchDetail.mockReset();
  window.sessionStorage.clear();
  vi.mocked(useAuthz).mockReturnValue({ isAdmin: true });

  vi.mocked(useMcpServers).mockReturnValue({
    data: servers,
    error: null,
    loading: false,
    refetch: refetchServers,
  });

  vi.mocked(useMcpServerDetail).mockImplementation((serverId) => ({
    data: serverId ? detailById[serverId] ?? null : null,
    error: null,
    loading: false,
    refetch: refetchDetail,
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
  vi.restoreAllMocks();
});

describe("McpPage", () => {
  it("renders mcp workspace through /mcp route", () => {
    window.history.pushState({}, "", "/mcp");
    render(<App />);

    expect(screen.getByRole("heading", { name: "MCP 管理" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "MCP 服务列表" })).toBeInTheDocument();
  });

  it("renders the shared workspace sidebar with MCP marked active", () => {
    renderMcpPage();

    const sidebar = screen.getByRole("complementary", {
      name: "工作台侧边栏",
    });
    const nav = within(sidebar).getByRole("navigation", {
      name: "工作台导航",
    });

    expect(
      within(nav).getByRole("button", { name: "发起新SOP质检" }),
    ).toBeInTheDocument();
    expect(
      within(nav).getByRole("button", { name: "MCP 管理" }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("keeps the server list and detail visible after toggling the sidebar", () => {
    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));
    expect(
      screen.getByRole("list", { name: "MCP 服务列表" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "MCP 服务详情" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "MCP 管理" }),
    ).toBeInTheDocument();
  });

  it("renders server list in left panel", () => {
    renderMcpPage();

    const list = screen.getByRole("list", { name: "MCP 服务列表" });

    expect(within(list).getByText("Alpha Server")).toBeInTheDocument();
    expect(within(list).getByText("Beta Server")).toBeInTheDocument();
  });

  it("switches right detail when clicking list item", () => {
    renderMcpPage();

    const detail = screen.getByRole("region", { name: "MCP 服务详情" });
    expect(within(detail).getByRole("heading", { name: "Alpha Server" }))
      .toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "选择服务 Beta Server" }));

    expect(within(detail).getByRole("heading", { name: "Beta Server" }))
      .toBeInTheDocument();
  });

  it("shows tools after switching to tools snapshot tab", () => {
    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "选择服务 Beta Server" }));
    fireEvent.click(screen.getByRole("tab", { name: "工具快照" }));

    const toolsList = screen.getByRole("list", { name: "工具快照列表" });
    expect(within(toolsList).getByText("beta.lookup")).toBeInTheDocument();
    expect(within(toolsList).getByText("beta.diff")).toBeInTheDocument();
  });

  it("invokes start stop restart check actions", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "启动 Alpha Server" }));
    fireEvent.click(screen.getByRole("button", { name: "停止 Alpha Server" }));
    fireEvent.click(screen.getByRole("button", { name: "重启 Alpha Server" }));
    fireEvent.click(screen.getByRole("button", { name: "检查 Alpha Server" }));

    expect(startServer).toHaveBeenCalledWith("srv-1");
    expect(stopServer).toHaveBeenCalledWith("srv-1");
    expect(restartServer).toHaveBeenCalledWith("srv-1");
    expect(checkServer).toHaveBeenCalledWith("srv-1");
  });

  it("shows clear Chinese message for 409 update conflicts", () => {
    vi.mocked(useMcpMutations).mockReturnValue({
      checkServer,
      createServer,
      deleteServer,
      error: new ApiError(409, "Conflict", "server is running"),
      pending: false,
      restartServer,
      startServer,
      stopServer,
      updateServer,
    });

    renderMcpPage();

    expect(screen.getByRole("alert")).toHaveTextContent("请先停止服务再修改配置");
  });

  it("asks for confirmation before delete and restart", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "重启 Alpha Server" }));
    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    expect(confirmSpy).toHaveBeenCalledTimes(2);
    expect(confirmSpy).toHaveBeenNthCalledWith(1, "确认重启 Alpha Server？");
    expect(confirmSpy).toHaveBeenNthCalledWith(2, "确认删除 Alpha Server？");
    expect(restartServer).not.toHaveBeenCalled();
    expect(deleteServer).not.toHaveBeenCalled();
  });

  it("does not confirm or delete while selected detail belongs to a previous server", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(useMcpServerDetail).mockImplementation((serverId) => ({
      data: serverId ? detailById["srv-1"] : null,
      error: null,
      loading: false,
      refetch: refetchDetail,
    }));

    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "选择服务 Beta Server" }));

    const deleteButton = screen.queryByRole("button", { name: "删除" });
    if (deleteButton) {
      fireEvent.click(deleteButton);
    }

    expect(confirmSpy).not.toHaveBeenCalled();
    expect(deleteServer).not.toHaveBeenCalled();
  });

  it("stores the MCP admin token and refetches the selected server data", async () => {
    renderMcpPage();

    expect(
      await screen.findByRole("heading", { name: "Alpha Server" }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("MCP Admin Token"), {
      target: { value: "token-from-ui" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Token" }));

    await waitFor(() => expect(refetchServers).toHaveBeenCalledTimes(1));
    expect(refetchDetail).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem("mcp-admin-token")).toBe("token-from-ui");
  });

  it("reloads failed list data after saving a non-empty admin token", async () => {
    vi.mocked(useMcpServers).mockImplementation(() => {
      const [state, setState] = useState({
        data: [] as McpServerSummary[],
        error: new ApiError(403, "Forbidden", "missing token") as Error | null,
        loading: false,
      });

      return {
        ...state,
        refetch: async () => {
          refetchServers();
          setState({ data: servers, error: null, loading: false });
        },
      };
    });
    vi.mocked(useMcpServerDetail).mockReturnValue({
      data: null,
      error: null,
      loading: false,
      refetch: refetchDetail,
    });

    renderMcpPage();

    expect(screen.getByRole("alert")).toHaveTextContent("missing token");
    expect(screen.queryByText("Alpha Server")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("MCP Admin Token"), {
      target: { value: "token-from-ui" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Token" }));

    await waitFor(() => expect(refetchServers).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Alpha Server")).toBeInTheDocument();
    expect(window.sessionStorage.getItem("mcp-admin-token")).toBe("token-from-ui");
  });

  it("shows detail load errors before the empty selected state", () => {
    render(
      <McpServerDetail
        activeTab="configuration"
        error={new ApiError(404, "Not Found", "missing server")}
        loading={false}
        onDeleteServer={vi.fn()}
        onEditServer={vi.fn()}
        onTabChange={vi.fn()}
        pending={false}
        server={null}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("MCP 服务不存在");
    expect(screen.queryByText("请选择一个 MCP 服务。")).not.toBeInTheDocument();
  });

  it("clears selected server after detail returns 404", async () => {
    vi.mocked(useMcpServerDetail).mockImplementation((serverId) => {
      if (serverId === "srv-1") {
        return {
          data: null,
          error: new ApiError(404, "Not Found", "missing server"),
          loading: false,
          refetch: vi.fn(),
        };
      }

      return {
        data: null,
        error: null,
        loading: false,
        refetch: refetchDetail,
      };
    });

    renderMcpPage();

    await waitFor(() => {
      const detailCalls = vi
        .mocked(useMcpServerDetail)
        .mock.calls.map(([serverId]) => serverId);

      expect(detailCalls).toContain("srv-1");
      expect(detailCalls[detailCalls.length - 1]).toBeNull();
    });
  });

  it("keeps current detail when non-selected row mutation returns 404", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    restartServer.mockRejectedValueOnce(new ApiError(404, "Not Found", "missing server"));

    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "重启 Beta Server" }));

    await waitFor(() => expect(restartServer).toHaveBeenCalledWith("srv-2"));
    await waitFor(() => expect(refetchServers).toHaveBeenCalled());

    const detail = screen.getByRole("region", { name: "MCP 服务详情" });
    expect(within(detail).getByRole("heading", { name: "Alpha Server" }))
      .toBeInTheDocument();
  });

  it("clears selected server on successful delete without refetching deleted detail", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteServer.mockResolvedValueOnce(undefined);
    refetchDetail.mockRejectedValueOnce(new ApiError(404, "Not Found", "deleted"));

    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    await waitFor(() => expect(deleteServer).toHaveBeenCalledWith("srv-1"));
    await waitFor(() => expect(refetchServers).toHaveBeenCalled());

    expect(refetchDetail).not.toHaveBeenCalled();
    expect(screen.getByText("请选择一个 MCP 服务。")).toBeInTheDocument();
  });

  it("shows inline error for empty name and prevents create", () => {
    renderMcpPage();
    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    const nameInput = within(dialog).getByLabelText("服务名称");

    fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent("请填写服务名称。");
    expect(nameInput).toHaveFocus();
    expect(createServer).not.toHaveBeenCalled();
  });

  it("validates required command for stdio and closes drawer on Escape", () => {
    renderMcpPage();
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

  it("validates invalid http url before submit", () => {
    renderMcpPage();
    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    fireEvent.change(within(dialog).getByLabelText("服务名称"), {
      target: { value: "Delta Server" },
    });
    fireEvent.change(within(dialog).getByLabelText("传输方式"), {
      target: { value: "http" },
    });

    const urlInput = within(dialog).getByLabelText("url");
    fireEvent.change(urlInput, {
      target: { value: "not-a-url" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "请填写有效的 http url。",
    );
    expect(urlInput).toHaveFocus();
    expect(createServer).not.toHaveBeenCalled();
  });

  it("creates server with parsed args env headers and conservative defaults", async () => {
    renderMcpPage();
    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    fireEvent.change(within(dialog).getByLabelText("服务名称"), {
      target: { value: "Gamma Server" },
    });
    fireEvent.change(within(dialog).getByLabelText("command"), {
      target: { value: "uvx" },
    });
    fireEvent.change(within(dialog).getByLabelText("args"), {
      target: { value: "--from\nmcp-package\nserve" },
    });
    fireEvent.change(within(dialog).getByLabelText("env"), {
      target: { value: "API_KEY=secret\nEMPTY=" },
    });
    fireEvent.change(within(dialog).getByLabelText("headers"), {
      target: { value: "Authorization=Bearer token" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));

    await waitFor(() => expect(createServer).toHaveBeenCalled());
    expect(createServer).toHaveBeenCalledWith({
      args: ["--from", "mcp-package", "serve"],
      command: "uvx",
      desired_state: "stopped",
      enabled: false,
      env: { API_KEY: "secret", EMPTY: "" },
      headers: { Authorization: "Bearer token" },
      name: "Gamma Server",
      transport: "stdio",
    });
  });

  it("shows inline validation for malformed key value config lines", () => {
    renderMcpPage();
    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    fireEvent.change(within(dialog).getByLabelText("服务名称"), {
      target: { value: "Gamma Server" },
    });
    fireEvent.change(within(dialog).getByLabelText("command"), {
      target: { value: "uvx" },
    });
    fireEvent.change(within(dialog).getByLabelText("env"), {
      target: { value: "BROKEN_LINE" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "env 第 1 行需要使用 KEY=VALUE 格式。",
    );
    expect(createServer).not.toHaveBeenCalled();
  });

  it("omits unchanged redacted env and headers when updating", async () => {
    renderMcpPage();

    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    const dialog = screen.getByRole("dialog", { name: "编辑 MCP 服务" });

    expect(within(dialog).getByLabelText("env")).toHaveValue("API_KEY=********");
    expect(within(dialog).getByLabelText("headers")).toHaveValue(
      "Authorization=********",
    );

    fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));

    await waitFor(() => expect(updateServer).toHaveBeenCalled());
    const payload = updateServer.mock.calls[0]?.[1] as Record<string, unknown>;

    expect(payload.args).toEqual(["--alpha"]);
    expect(payload).not.toHaveProperty("env");
    expect(payload).not.toHaveProperty("headers");
  });

  it("wraps focus within drawer on Tab and Shift+Tab", () => {
    renderMcpPage();
    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    const closeButton = within(dialog).getByRole("button", { name: "关闭" });
    const saveButton = within(dialog).getByRole("button", { name: "保存" });

    saveButton.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(closeButton).toHaveFocus();

    closeButton.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(saveButton).toHaveFocus();
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

function buildDetail(
  overrides: Partial<McpServerDetailType> = {},
): McpServerDetailType {
  return {
    ...buildSummary(overrides),
    tools: [],
    ...overrides,
  };
}

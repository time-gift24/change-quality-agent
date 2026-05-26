// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useMcpMutations, useMcpServerDetail } from "../hooks";
import type { McpServerDetail } from "../types";
import { McpCreatePage, McpEditPage } from "./McpServerFormPage";

const detail: McpServerDetail = {
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
  tools: [],
  transport: "stdio",
  url: null,
};

const createServer = vi.fn();
const updateServer = vi.fn();
const refetchDetail = vi.fn();

vi.mock("../hooks", () => ({
  useMcpMutations: vi.fn(),
  useMcpServerDetail: vi.fn(),
}));

function renderCreatePage() {
  return render(
    <MemoryRouter initialEntries={["/mcp/new"]}>
      <Routes>
        <Route element={<McpCreatePage />} path="/mcp/new" />
        <Route element={<div>创建后详情页</div>} path="/mcp/:serverId" />
      </Routes>
    </MemoryRouter>,
  );
}

function renderEditPage() {
  return render(
    <MemoryRouter initialEntries={["/mcp/srv-1/edit"]}>
      <Routes>
        <Route element={<McpEditPage />} path="/mcp/:serverId/edit" />
        <Route element={<div>编辑后详情页</div>} path="/mcp/:serverId" />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  createServer.mockReset();
  updateServer.mockReset();
  refetchDetail.mockReset();

  createServer.mockResolvedValue({ ...detail, id: "srv-new", name: "Gamma Server" });
  updateServer.mockResolvedValue(detail);

  vi.mocked(useMcpServerDetail).mockReturnValue({
    data: detail,
    error: null,
    loading: false,
    refetch: refetchDetail,
  });

  vi.mocked(useMcpMutations).mockReturnValue({
    checkServer: vi.fn(),
    createServer,
    deleteServer: vi.fn(),
    error: null,
    pending: false,
    restartServer: vi.fn(),
    startServer: vi.fn(),
    stopServer: vi.fn(),
    updateServer,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("McpServerFormPage", () => {
  it("renders create page with breadcrumb and page form", () => {
    renderCreatePage();

    const nav = screen.getByRole("navigation", { name: "面包屑" });
    expect(within(nav).getByRole("link", { name: "MCP 管理" })).toHaveAttribute("href", "/mcp");
    expect(within(nav).getByText("新增 Server")).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "新增 MCP Server" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("creates a server from the create page form", async () => {
    renderCreatePage();

    fireEvent.change(screen.getByRole("textbox", { name: /服务名称/ }), {
      target: { value: "Gamma Server" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: /command/ }), {
      target: { value: "uvx" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(createServer).toHaveBeenCalled());
    expect(createServer).toHaveBeenCalledWith(expect.objectContaining({
      command: "uvx",
      name: "Gamma Server",
      transport: "stdio",
    }));
    expect(await screen.findByText("创建后详情页")).toBeInTheDocument();
  });

  it("renders edit page with breadcrumb and populated editable form", () => {
    renderEditPage();

    const nav = screen.getByRole("navigation", { name: "面包屑" });
    expect(within(nav).getByRole("link", { name: "MCP 管理" })).toHaveAttribute("href", "/mcp");
    expect(within(nav).getByRole("link", { name: "Alpha Server" })).toHaveAttribute("href", "/mcp/srv-1");
    expect(within(nav).getByText("编辑")).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "编辑 MCP Server" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /服务名称/ })).toHaveValue("Alpha Server");
    expect(screen.getByRole("textbox", { name: /服务名称/ })).not.toHaveAttribute("readonly");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

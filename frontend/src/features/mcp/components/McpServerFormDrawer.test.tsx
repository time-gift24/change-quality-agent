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
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { McpServerFormDrawer } from "./McpServerFormDrawer";
import type { McpServerDetail } from "../types";

const server: McpServerDetail = {
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

function renderCreateDrawer(overrides: Partial<React.ComponentProps<typeof McpServerFormDrawer>> = {}) {
  const onClose = vi.fn();
  const onCreate = vi.fn().mockResolvedValue(undefined);
  const onUpdate = vi.fn().mockResolvedValue(undefined);

  render(
    <MemoryRouter initialEntries={["/mcp/new"]}>
      <McpServerFormDrawer
        mode="create"
        onClose={onClose}
        onCreate={onCreate}
        onUpdate={onUpdate}
        open={true}
        pending={false}
        server={null}
        {...overrides}
      />
    </MemoryRouter>,
  );

  return { onClose, onCreate, onUpdate };
}

function renderEditDrawer(overrides: Partial<React.ComponentProps<typeof McpServerFormDrawer>> = {}) {
  const onClose = vi.fn();
  const onCreate = vi.fn().mockResolvedValue(undefined);
  const onUpdate = vi.fn().mockResolvedValue(undefined);

  render(
    <MemoryRouter initialEntries={["/mcp/srv-1/edit"]}>
      <McpServerFormDrawer
        mode="edit"
        onClose={onClose}
        onCreate={onCreate}
        onUpdate={onUpdate}
        open={true}
        pending={false}
        server={server}
        {...overrides}
      />
    </MemoryRouter>,
  );

  return { onClose, onCreate, onUpdate };
}

afterEach(() => {
  cleanup();
});

describe("McpServerFormDrawer", () => {
  it("shows inline error for empty name and prevents create", () => {
    const { onCreate } = renderCreateDrawer();

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(screen.getByRole("alert")).toHaveTextContent("请填写服务名称。");
    expect(screen.getByLabelText(/服务名称/)).toHaveFocus();
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("validates required command for stdio and closes drawer on Escape", () => {
    const { onClose } = renderCreateDrawer();

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Gamma Server" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(screen.getByRole("alert")).toHaveTextContent("stdio 模式需要填写 command。");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("validates invalid http url before submit", () => {
    renderCreateDrawer();

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Delta Server" },
    });
    fireEvent.change(screen.getByLabelText("传输方式"), {
      target: { value: "http" },
    });

    const urlInput = screen.getByLabelText(/url/);
    fireEvent.change(urlInput, { target: { value: "not-a-url" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(screen.getByRole("alert")).toHaveTextContent("请填写有效的 http url。");
    expect(urlInput).toHaveFocus();
  });

  it("creates server with parsed args env headers and conservative defaults", async () => {
    const onClose = vi.fn();
    const onCreate = vi.fn().mockResolvedValue({ id: "new-srv" });

    render(
      <MemoryRouter initialEntries={["/mcp/new"]}>
        <McpServerFormDrawer
          mode="create"
          onClose={onClose}
          onCreate={onCreate}
          onUpdate={vi.fn().mockResolvedValue(undefined)}
          open={true}
          pending={false}
          server={null}
        />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Gamma Server" },
    });
    fireEvent.change(screen.getByLabelText(/command/), {
      target: { value: "uvx" },
    });
    fireEvent.change(screen.getByLabelText(/args/), {
      target: { value: "--from\nmcp-package\nserve" },
    });
    fireEvent.change(screen.getByLabelText(/env/), {
      target: { value: "API_KEY=secret\nEMPTY=" },
    });
    fireEvent.change(screen.getByLabelText(/headers/), {
      target: { value: "Authorization=Bearer token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    expect(onCreate).toHaveBeenCalledWith({
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
    renderCreateDrawer();

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Gamma Server" },
    });
    fireEvent.change(screen.getByLabelText(/command/), {
      target: { value: "uvx" },
    });
    fireEvent.change(screen.getByLabelText(/env/), {
      target: { value: "BROKEN_LINE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(screen.getByRole("alert")).toHaveTextContent("env 第 1 行需要使用 KEY=VALUE 格式。");
  });

  it("omits unchanged redacted env and headers when updating", async () => {
    const { onUpdate } = renderEditDrawer();

    expect(screen.getByLabelText(/env/)).toHaveValue("API_KEY=********");
    expect(screen.getByLabelText(/headers/)).toHaveValue("Authorization=********");

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    const payload = onUpdate.mock.calls[0]?.[1] as Record<string, unknown>;

    expect(payload.args).toEqual(["--alpha"]);
    expect(payload).not.toHaveProperty("env");
    expect(payload).not.toHaveProperty("headers");
  });

  it("wraps focus within drawer on Tab and Shift+Tab", () => {
    renderCreateDrawer();

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

  it("shows NEW SERVER label in create mode", () => {
    renderCreateDrawer();
    expect(screen.getByText("NEW SERVER")).toBeInTheDocument();
  });

  it("shows EDIT · serverId label in edit mode", () => {
    renderEditDrawer();
    expect(screen.getByText("EDIT · srv-1")).toBeInTheDocument();
  });

  it("uses checkbox for desired_state", () => {
    renderCreateDrawer();
    const checkbox = screen.getByLabelText(/创建后立即启动/);
    expect(checkbox).toBeInstanceOf(HTMLInputElement);
    expect((checkbox as HTMLInputElement).type).toBe("checkbox");
  });
});

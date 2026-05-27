// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { McpRowActionsMenu } from "./McpRowActionsMenu";
import type { McpServerRuntimeStatus } from "../types";

function renderMenu(status: McpServerRuntimeStatus = "running", overrides: Partial<React.ComponentProps<typeof McpRowActionsMenu>> = {}) {
  const props = {
    runtimeStatus: status,
    serverId: "srv-1",
    serverName: "Alpha Server",
    onStart: vi.fn(),
    onStop: vi.fn(),
    onRestart: vi.fn(),
    onCheck: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  return {
    ...render(
      <MemoryRouter>
        <McpRowActionsMenu {...props} />
      </MemoryRouter>,
    ),
    props,
  };
}

afterEach(() => {
  cleanup();
});

describe("McpRowActionsMenu", () => {
  it("renders trigger button with aria-haspopup", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("opens menu on ArrowDown and focuses first item", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    const menu = screen.getByRole("menu");
    expect(menu).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menuitem", { name: "查看详情" })).toHaveFocus();
  });

  it("opens menu on Enter and focuses first item", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "Enter" });

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "查看详情" })).toHaveFocus();
  });

  it("opens menu on ArrowUp and focuses last item", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowUp" });

    expect(screen.getByRole("menu")).toBeInTheDocument();
    const items = screen.getAllByRole("menuitem");
    expect(items[items.length - 1]).toHaveFocus();
  });

  it("closes menu on Escape and returns focus to trigger", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("closes menu on click outside", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    fireEvent.mouseDown(document.body);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("navigates items with ArrowDown and ArrowUp", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    const items = screen.getAllByRole("menuitem");
    fireEvent.keyDown(screen.getByRole("menu"), { key: "ArrowDown" });
    expect(items[1]).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("menu"), { key: "ArrowUp" });
    expect(items[0]).toHaveFocus();
  });

  it("jumps to first/last with Home/End", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    const items = screen.getAllByRole("menuitem");
    fireEvent.keyDown(screen.getByRole("menu"), { key: "End" });
    expect(items[items.length - 1]).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("menu"), { key: "Home" });
    expect(items[0]).toHaveFocus();
  });

  it("shows 查看详情 as a link to detail page", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    const detailLink = screen.getByRole("menuitem", { name: "查看详情" });
    expect(detailLink.tagName).toBe("A");
    expect(detailLink).toHaveAttribute("href", "/mcp/srv-1");
  });

  it("shows 启动 for stopped server, hides for running", () => {
    renderMenu("stopped");
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    expect(screen.getByRole("menuitem", { name: "启动" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "停止" })).not.toBeInTheDocument();
  });

  it("shows 停止 for running server, hides 启动", () => {
    renderMenu("running");
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    expect(screen.getByRole("menuitem", { name: "停止" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "启动" })).not.toBeInTheDocument();
  });

  it("calls onRestart when 重启 is clicked", () => {
    const { props } = renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    fireEvent.click(screen.getByRole("menuitem", { name: "重启" }));
    expect(props.onRestart).toHaveBeenCalledWith("srv-1");
  });

  it("closes menu after selecting an action", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    fireEvent.click(screen.getByRole("menuitem", { name: "检查" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens menu on Space and prevents default scroll behavior", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: " " });

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "查看详情" })).toHaveFocus();
  });
});

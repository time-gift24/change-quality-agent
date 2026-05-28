// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { WorkspaceSidebar } from "./WorkspaceSidebar";
import { workspaceSidebarRoutes } from "./routing/workspaceRoutes";

function renderSidebar(overrides: Partial<React.ComponentProps<typeof WorkspaceSidebar>> = {}) {
  const props = {
    activeKey: "sop" as const,
    navRoutes: [...workspaceSidebarRoutes],
    onNavigate: vi.fn(),
    onNewConversation: vi.fn(),
    onToggle: vi.fn(),
    open: true,
    ...overrides,
  };
  return {
    ...render(
      <MemoryRouter>
        <WorkspaceSidebar {...props} />
      </MemoryRouter>,
    ),
    props,
  };
}

afterEach(() => {
  cleanup();
});

describe("WorkspaceSidebar", () => {
  it("renders both 发起新SOP质检 and MCP 管理 entries when expanded", () => {
    renderSidebar({ open: true });

    expect(
      screen.getByRole("button", { name: "发起新SOP质检" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "MCP 管理" })).toBeInTheDocument();
  });

  it("places MCP 管理 directly below 发起新SOP质检 inside the same nav", () => {
    renderSidebar({ open: true });

    const nav = screen.getByRole("navigation", { name: "工作台导航" });
    const buttons = nav.querySelectorAll("button");

    expect(buttons[0]).toHaveAccessibleName("发起新SOP质检");
    expect(buttons[1]).toHaveAccessibleName("MCP 管理");
  });

  it("keeps both nav entries visible (with icons) when collapsed", () => {
    renderSidebar({ open: false });

    const newSopButton = screen.getByRole("button", { name: "发起新SOP质检" });
    const mcpButton = screen.getByRole("button", { name: "MCP 管理" });

    expect(newSopButton).toBeInTheDocument();
    expect(mcpButton).toBeInTheDocument();
    expect(newSopButton.querySelector("svg")).not.toBeNull();
    expect(mcpButton.querySelector("svg")).not.toBeNull();
  });

  it("hides MCP 管理 when routing does not expose that nav route", () => {
    renderSidebar({ navRoutes: [workspaceSidebarRoutes[0]] });

    expect(
      screen.getByRole("button", { name: "发起新SOP质检" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "MCP 管理" }),
    ).not.toBeInTheDocument();
  });

  it("hides the 质量检查 brand text when collapsed but keeps the toggle", () => {
    renderSidebar({ open: false });

    expect(screen.queryByText("质量检查")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "展开侧边栏" }),
    ).toBeInTheDocument();
  });

  it("fires onToggle when the toggle button is clicked", () => {
    const { props } = renderSidebar({ open: true });

    fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));

    expect(props.onToggle).toHaveBeenCalledTimes(1);
  });

  it("uses the same collapsed and expanded widths as ChatPage's sidebar", () => {
    const { container } = renderSidebar({ open: false });
    const collapsedAside = container.querySelector("aside");
    expect(collapsedAside?.className).toContain("w-14");

    cleanup();
    const { container: openContainer } = renderSidebar({ open: true });
    const openAside = openContainer.querySelector("aside");
    expect(openAside?.className).toContain("w-64");
  });

  it("invokes onNavigate when MCP 管理 is clicked from a non-mcp page", () => {
    const { props } = renderSidebar({ activeKey: "sop" });

    fireEvent.click(screen.getByRole("button", { name: "MCP 管理" }));

    expect(props.onNavigate).toHaveBeenCalledWith("mcp");
  });

  it("invokes onNewConversation when on sop and 发起新SOP质检 is clicked", () => {
    const { props } = renderSidebar({ activeKey: "sop" });

    fireEvent.click(screen.getByRole("button", { name: "发起新SOP质检" }));

    expect(props.onNewConversation).toHaveBeenCalledTimes(1);
    expect(props.onNavigate).not.toHaveBeenCalled();
  });

  it("invokes onNavigateSop when on mcp and 发起新SOP质检 is clicked", () => {
    const { props } = renderSidebar({
      activeKey: "mcp",
      onNewConversation: vi.fn(),
    });

    fireEvent.click(screen.getByRole("button", { name: "发起新SOP质检" }));

    expect(props.onNavigate).toHaveBeenCalledWith("sop");
    expect(props.onNewConversation).not.toHaveBeenCalled();
  });

  it("marks the active key with aria-current", () => {
    renderSidebar({ activeKey: "mcp" });

    expect(
      screen.getByRole("button", { name: "MCP 管理" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("button", { name: "发起新SOP质检" }),
    ).not.toHaveAttribute("aria-current");
  });
});

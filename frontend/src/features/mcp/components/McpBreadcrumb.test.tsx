// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { McpBreadcrumb } from "./McpBreadcrumb";

afterEach(() => {
  cleanup();
});

describe("McpBreadcrumb", () => {
  it("renders two-segment breadcrumb with server name", () => {
    render(
      <MemoryRouter>
        <McpBreadcrumb serverName="Alpha Server" />
      </MemoryRouter>,
    );

    const nav = screen.getByRole("navigation", { name: "面包屑" });
    expect(nav).toBeInTheDocument();

    const listLink = screen.getByRole("link", { name: "MCP 管理" });
    expect(listLink).toHaveAttribute("href", "/mcp");

    expect(screen.getByText("Alpha Server")).toBeInTheDocument();
    expect(screen.getByText("Alpha Server")).toHaveAttribute("aria-current", "page");
  });

  it("renders custom breadcrumb segments for page actions", () => {
    render(
      <MemoryRouter>
        <McpBreadcrumb
          items={[
            { label: "MCP 管理", to: "/mcp" },
            { label: "Alpha Server", to: "/mcp/srv-1" },
            { label: "编辑" },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "MCP 管理" })).toHaveAttribute("href", "/mcp");
    expect(screen.getByRole("link", { name: "Alpha Server" })).toHaveAttribute("href", "/mcp/srv-1");
    expect(screen.getByText("编辑")).toHaveAttribute("aria-current", "page");
  });

  it("truncates long server names", () => {
    render(
      <MemoryRouter>
        <McpBreadcrumb serverName="Very Long Server Name That Should Truncate" />
      </MemoryRouter>,
    );

    const current = screen.getByText("Very Long Server Name That Should Truncate");
    expect(current.className).toContain("truncate");
  });
});

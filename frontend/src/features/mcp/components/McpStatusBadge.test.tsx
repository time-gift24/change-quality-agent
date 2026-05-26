// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { McpStatusBadge } from "./McpStatusBadge";

afterEach(() => {
  cleanup();
});

describe("McpStatusBadge", () => {
  it("renders running badge with green dot", () => {
    render(<McpStatusBadge status="running" />);
    const badge = screen.getByText("running");
    expect(badge).toBeInTheDocument();
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "running");
  });

  it("renders stopped badge with gray dot", () => {
    render(<McpStatusBadge status="stopped" />);
    expect(screen.getByText("stopped")).toBeInTheDocument();
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "stopped");
  });

  it("renders error badge with red dot", () => {
    render(<McpStatusBadge status="error" />);
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("renders starting badge", () => {
    render(<McpStatusBadge status="starting" />);
    expect(screen.getByText("starting")).toBeInTheDocument();
  });

  it("renders unknown badge", () => {
    render(<McpStatusBadge status="unknown" />);
    expect(screen.getByText("unknown")).toBeInTheDocument();
  });
});

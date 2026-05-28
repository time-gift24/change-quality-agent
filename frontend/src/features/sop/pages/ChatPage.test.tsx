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

import { App } from "../../../app/App";

vi.mock("../../../app/routing/useAuthz", () => ({
  useAuthz: () => ({ isAdmin: true }),
}));

vi.mock("../../mcp/pages/McpPage", () => ({
  McpPage: () => (
    <div role="region" aria-label="MCP 管理 mock">
      <h1>MCP 管理</h1>
    </div>
  ),
}));

function renderAppAt(path = "/sop") {
  window.history.pushState({}, "", path);
  return render(<App />);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ChatPage", () => {
  it("renders chat page on /sop", async () => {
    vi.stubGlobal("fetch", fetchByRequest());
    renderAppAt();
    expect(
      await screen.findByRole("form", { name: "SOP 运行表单" }),
    ).toBeInTheDocument();
  });

  it("loads seeded mock history without pre-filling the SOP input", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    renderAppAt();

    expect(await screen.findByPlaceholderText("输入 SOP ID")).toHaveValue("");
    expect(
      await screen.findByRole("button", { name: "release-checklist" }),
    ).toBeInTheDocument();
  });

  it("uses a concise SOP ID placeholder", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    renderAppAt();

    expect(await screen.findByPlaceholderText("输入 SOP ID")).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("输入 SOP ID,例如 release-checklist"),
    ).not.toBeInTheDocument();
  });

  it("renders the environment select as a polished native control", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    renderAppAt();

    const select = await screen.findByLabelText("环境");

    expect(select.className).toContain("appearance-none");
    expect(select.className).toContain("shadow-sm");
    expect(screen.getByTestId("environment-select-chevron"))
      .toBeInTheDocument();
  });

  it("places the recent history chevron on the right side", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    renderAppAt();

    const button = await screen.findByRole("button", {
      name: "切换最近质检SOP",
    });
    const label = screen.getByText("最近质检SOP");
    const chevron = button.querySelector("svg");

    expect(button.className).toContain("justify-between");
    expect(chevron).not.toBeNull();
    expect(
      label.compareDocumentPosition(chevron!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("scrolls recent history to the bottom after loading", async () => {
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        return 480;
      },
    });
    vi.stubGlobal("fetch", fetchByRequest());

    renderAppAt();

    await screen.findByRole("button", { name: "release-checklist" });
    const scrollArea = screen.getByTestId("recent-sop-scroll-area");

    await waitFor(() => {
      expect(scrollArea.scrollTop).toBe(480);
    });
  });

  it("shows the MCP 管理 entry inside the same sidebar as 发起新SOP质检", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    renderAppAt();

    const sidebar = await screen.findByRole("complementary", {
      name: "工作台侧边栏",
    });
    const nav = await within(sidebar).findByRole("navigation", {
      name: "工作台导航",
    });

    expect(
      within(nav).getByRole("button", { name: "发起新SOP质检" }),
    ).toBeInTheDocument();
    expect(
      within(nav).getByRole("button", { name: "MCP 管理" }),
    ).toBeInTheDocument();
  });

  it("collapses and expands the sidebar while keeping both nav entries visible", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    renderAppAt();

    const collapse = await screen.findByRole("button", {
      name: "收起侧边栏",
    });
    fireEvent.click(collapse);

    expect(
      screen.getByRole("button", { name: "展开侧边栏" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "MCP 管理" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "发起新SOP质检" }),
    ).toBeInTheDocument();

    const aside = screen.getByRole("complementary", { name: "工作台侧边栏" });
    expect(aside.className).toContain("w-14");

    fireEvent.click(screen.getByRole("button", { name: "展开侧边栏" }));
    expect(aside.className).toContain("w-64");
  });

  it("navigates to /mcp when MCP 管理 is clicked in the sidebar", async () => {
    vi.stubGlobal("fetch", fetchByRequest());
    renderAppAt();

    const sidebar = await screen.findByRole("complementary", {
      name: "工作台侧边栏",
    });
    fireEvent.click(
      within(sidebar).getByRole("button", { name: "MCP 管理" }),
    );

    expect(
      await screen.findByRole("heading", { name: "MCP 管理" }),
    ).toBeInTheDocument();
  });
});

function fetchByRequest() {
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input);

    if (url === "/api/auth/me") {
      return Promise.resolve(
        jsonResponse({
          id: "user-admin",
          account: "admin",
          is_admin: true,
          meta: {},
        }),
      );
    }

    if (url === "/api/sop/environments") {
      return Promise.resolve(
        jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "开发环境" },
        ]),
      );
    }

    if (url === "/api/sop/recent/runs?env=dev&limit=50") {
      return Promise.resolve(
        jsonResponse([
          {
            run_id: "run-1",
            subject_id: "release-checklist",
            status: "success",
            created_at: "2026-05-26T00:00:00Z",
          },
        ]),
      );
    }

    if (url.startsWith("/api/sop/") && url.endsWith("/runs?env=dev")) {
      return Promise.resolve(jsonResponse([]));
    }

    if (url === "/api/mcp/servers") {
      return Promise.resolve(jsonResponse([]));
    }

    throw new Error(`Unexpected fetch: ${url}`);
  });
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

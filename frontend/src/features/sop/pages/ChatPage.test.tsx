// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatPage } from "./ChatPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ChatPage", () => {
  it("loads seeded mock history without pre-filling the SOP input", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    render(<ChatPage />);

    expect(await screen.findByPlaceholderText("输入 SOP ID")).toHaveValue("");
    expect(
      await screen.findByRole("button", { name: "release-checklist" }),
    ).toBeInTheDocument();
  });

  it("uses a concise SOP ID placeholder", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    render(<ChatPage />);

    expect(await screen.findByPlaceholderText("输入 SOP ID")).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("输入 SOP ID,例如 release-checklist"),
    ).not.toBeInTheDocument();
  });

  it("renders the environment select as a polished native control", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    render(<ChatPage />);

    const select = await screen.findByLabelText("环境");

    expect(select.className).toContain("appearance-none");
    expect(select.className).toContain("shadow-sm");
    expect(screen.getByTestId("environment-select-chevron"))
      .toBeInTheDocument();
  });

  it("places the recent history chevron on the right side", async () => {
    vi.stubGlobal("fetch", fetchByRequest());

    render(<ChatPage />);

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
});

function fetchByRequest() {
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input);

    if (url === "/api/sop/environments") {
      return Promise.resolve(
        jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "开发环境" },
        ]),
      );
    }

    if (url === "/api/sop/release-checklist/runs?env=dev") {
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

    throw new Error(`Unexpected fetch: ${url}`);
  });
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

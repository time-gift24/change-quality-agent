// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { runObserverMock } = vi.hoisted(() => ({
  runObserverMock: vi.fn(),
}));

vi.mock("../../runs/components/RunObserver", () => ({
  RunObserver: ({
    runId,
    registeredNodeIds,
  }: {
    runId: string;
    registeredNodeIds?: string[];
  }) => {
    runObserverMock({ runId, registeredNodeIds });

    return (
      <section aria-label="Run observer" data-run-id={runId}>
        Observing {runId}
        <span data-testid="registered-nodes">
          {(registeredNodeIds ?? []).join(",")}
        </span>
      </section>
    );
  },
}));

import { SopQualityPage } from "./SopQualityPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("SopQualityPage", () => {
  it("loads environments into the selector", async () => {
    vi.stubGlobal(
      "fetch",
      fetchSequence([
        jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "开发环境" },
          { key: "prod", name_en: "Production", name_zh: "生产环境" },
        ]),
        jsonResponse({ runs: [] }),
      ]),
    );

    render(<SopQualityPage />);

    expect(
      await screen.findByRole("option", {
        name: "Development / 开发环境 (dev)",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Production / 生产环境 (prod)" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("SOP preview")).toHaveTextContent(
        "Development / 开发环境 (dev)",
      );
    });
  });

  it("announces environment load errors", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse(
          { message: "unavailable" },
          { status: 500, statusText: "Server Error" },
        ),
      }),
    );

    render(<SopQualityPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "API request failed: 500 Server Error",
    );
  });

  it("fetches preview without creating a run", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url === "/api/sop/environments") {
        return Promise.resolve(
          jsonResponse([
            { key: "dev", name_en: "Development", name_zh: "Development" },
          ]),
        );
      }

      if (url === "/api/sop/release-checklist?env=dev" && !init?.method) {
        return Promise.resolve(jsonResponse(sopPreview()));
      }

      if (url === "/api/sop/release-checklist/runs?env=dev" && !init?.method) {
        return Promise.resolve(jsonResponse({ runs: [] }));
      }

      return Promise.resolve(jsonResponse({ run_id: "unexpected" }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<SopQualityPage />);

    await screen.findByRole("option", { name: "Development (dev)" });
    expect(screen.queryByText("Release checklist")).not.toBeInTheDocument();
    const previewButton = screen.getByRole("button", { name: "Preview SOP" });

    await waitFor(() => {
      expect(previewButton).toBeEnabled();
    });
    fireEvent.click(previewButton);

    await screen.findByText("Release checklist");

    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/sop/release-checklist/runs?env=dev",
      expect.objectContaining({ method: "POST" }),
    );
    expect(screen.queryByLabelText("Run observer")).not.toBeInTheDocument();
  });

  it("starts observing the returned run for a 202 response", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist?env=dev": jsonResponse(sopPreview()),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse({ runs: [] }),
        "POST /api/sop/release-checklist/runs?env=dev": jsonResponse(
          { run_id: "run-202" },
          { status: 202 },
        ),
      }),
    );

    render(<SopQualityPage />);

    await screen.findByRole("option", { name: "Development (dev)" });
    fireEvent.click(await screen.findByRole("button", { name: "Start run" }));

    expect(await screen.findByText("Observing run-202")).toBeInTheDocument();
    expect(runObserverMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        runId: "run-202",
        registeredNodeIds: ["load_sop", "check_steps", "summarize_result"],
      }),
    );
    expect(runObserverMock.mock.lastCall?.[0]).not.toHaveProperty("env");
    expect(runObserverMock.mock.lastCall?.[0]).not.toHaveProperty("env_key");
  });

  it("switches to the active run id for a 409 response", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist?env=dev": jsonResponse(sopPreview()),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse({ runs: [] }),
        "POST /api/sop/release-checklist/runs?env=dev": jsonResponse(
          { active_run_id: "active-run" },
          { status: 409, statusText: "Conflict" },
        ),
      }),
    );

    render(<SopQualityPage />);

    await screen.findByRole("option", { name: "Development (dev)" });
    fireEvent.click(await screen.findByRole("button", { name: "Start run" }));

    expect(await screen.findByText("Observing active-run")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "An active run already exists. Joined active-run.",
    );
  });

  it("announces start errors with API status context", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse({ runs: [] }),
        "POST /api/sop/release-checklist/runs?env=dev": new Response("", {
          status: 500,
          statusText: "Server Error",
        }),
      }),
    );

    render(<SopQualityPage />);

    await screen.findByRole("option", { name: "Development (dev)" });
    const startButton = screen.getByRole("button", { name: "Start run" });

    await waitFor(() => {
      expect(startButton).toBeEnabled();
    });
    fireEvent.click(startButton);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "API request failed: 500 Server Error",
    );
  });

  it("announces preview errors", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse({ runs: [] }),
        "GET /api/sop/release-checklist?env=dev": jsonResponse(
          { message: "not found" },
          { status: 404, statusText: "Not Found" },
        ),
      }),
    );

    render(<SopQualityPage />);

    await screen.findByRole("option", { name: "Development (dev)" });
    const previewButton = screen.getByRole("button", { name: "Preview SOP" });

    await waitFor(() => {
      expect(previewButton).toBeEnabled();
    });
    fireEvent.click(previewButton);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "API request failed: 404 Not Found",
    );
  });

  it("announces history load errors", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse(
          { message: "bad gateway" },
          { status: 502, statusText: "Bad Gateway" },
        ),
      }),
    );

    render(<SopQualityPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "API request failed: 502 Bad Gateway",
    );
  });

  it("hides stale history while a new environment history is loading", async () => {
    const prodHistory = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/sop/environments") {
          return Promise.resolve(
            jsonResponse([
              { key: "dev", name_en: "Development", name_zh: "Development" },
              { key: "prod", name_en: "Production", name_zh: "Production" },
            ]),
          );
        }

        if (url === "/api/sop/release-checklist/runs?env=dev") {
          return Promise.resolve(
            jsonResponse({
              runs: [{ run_id: "dev-run", status: "success" }],
            }),
          );
        }

        if (url === "/api/sop/release-checklist/runs?env=prod") {
          return prodHistory.promise;
        }

        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<SopQualityPage />);

    expect(await screen.findByRole("button", { name: /dev-run/ }))
      .toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Environment"), {
      target: { value: "prod" },
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /dev-run/ }))
        .not.toBeInTheDocument();
    });
    expect(screen.getByLabelText("Run history")).toHaveTextContent("Loading");

    await prodHistory.resolve(
      jsonResponse({ runs: [{ run_id: "prod-run", status: "running" }] }),
    );
    expect(await screen.findByRole("button", { name: /prod-run/ }))
      .toBeInTheDocument();
  });

  it("shows hover feedback on primary SOP actions", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse({ runs: [] }),
      }),
    );

    render(<SopQualityPage />);

    await screen.findByRole("option", { name: "Development (dev)" });

    expect(screen.getByRole("button", { name: "Preview SOP" }).className)
      .toContain("hover:bg-[#f8f8f6]");
    expect(screen.getByRole("button", { name: "Start run" }).className)
      .toContain("hover:bg-[#003c33]");
  });

  it("clears the observed run when the SOP id changes", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse({
          runs: [{ run_id: "old-run", status: "success" }],
        }),
        "GET /api/sop/payment-checklist/runs?env=dev": jsonResponse({
          runs: [],
        }),
      }),
    );

    render(<SopQualityPage />);

    fireEvent.click(await screen.findByRole("button", { name: /old-run/ }));
    expect(await screen.findByText("Observing old-run")).toBeInTheDocument();

    const sopIdInput = screen.getByLabelText("SOP id");
    fireEvent.change(sopIdInput, { target: { value: "payment-checklist" } });

    expect(screen.queryByLabelText("Run observer")).not.toBeInTheDocument();
  });

  it("ignores a stale start response after the SOP id changes", async () => {
    const startResponse = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        const url = String(input);

        if (url === "/api/sop/environments") {
          return Promise.resolve(
            jsonResponse([
              { key: "dev", name_en: "Development", name_zh: "Development" },
            ]),
          );
        }

        if (method === "GET" && url.endsWith("/runs?env=dev")) {
          return Promise.resolve(jsonResponse({ runs: [] }));
        }

        if (
          method === "POST" &&
          url === "/api/sop/release-checklist/runs?env=dev"
        ) {
          return startResponse.promise;
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    render(<SopQualityPage />);

    await screen.findByRole("option", { name: "Development (dev)" });
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    fireEvent.change(screen.getByLabelText("SOP id"), {
      target: { value: "payment-checklist" },
    });

    await startResponse.resolve(jsonResponse({ run_id: "stale-run" }, { status: 202 }));

    expect(screen.queryByText("Observing stale-run")).not.toBeInTheDocument();
  });

  it("switches the observer run when a history item is clicked", async () => {
    vi.stubGlobal(
      "fetch",
      fetchByRequest({
        "GET /api/sop/environments": jsonResponse([
          { key: "dev", name_en: "Development", name_zh: "Development" },
        ]),
        "GET /api/sop/release-checklist?env=dev": jsonResponse(sopPreview()),
        "GET /api/sop/release-checklist/runs?env=dev": jsonResponse({
          runs: [
            { run_id: "newer-run", status: "success", created_at: "2026-05-25T11:00:00Z" },
            { run_id: "older-run", status: "error", created_at: "2026-05-25T10:00:00Z" },
          ],
        }),
      }),
    );

    render(<SopQualityPage />);

    fireEvent.click(await screen.findByRole("button", { name: /older-run/ }));

    await waitFor(() => {
      expect(screen.getByLabelText("Run observer")).toHaveAttribute(
        "data-run-id",
        "older-run",
      );
    });
  });
});

function sopPreview() {
  return {
    sop_id: "release-checklist",
    env_key: "dev",
    raw_payload: {
      title: "Release checklist",
      steps: ["Prepare release notes", "Verify rollout plan"],
    },
  };
}

function fetchSequence(responses: Response[]) {
  return vi.fn(() => {
    const response = responses.shift();

    if (!response) {
      throw new Error("Unexpected fetch");
    }

    return Promise.resolve(response);
  });
}

function fetchByRequest(responses: Record<string, Response>) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const key = `${method} ${String(input)}`;
    const response = responses[key];

    if (!response) {
      throw new Error(`Unexpected fetch: ${key}`);
    }

    return Promise.resolve(response);
  });
}

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
    ...init,
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });

  return { promise, resolve };
}

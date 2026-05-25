// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createInitialRunViewState,
  reduceRunEvent,
  type RunViewState,
} from "../reducer";
import type { RunEvent, RunSummary } from "../types";
import { RunEventStream } from "./RunEventStream";
import { RunNodeList } from "./RunNodeList";
import { RunObserver } from "./RunObserver";
import { RunStatusBar } from "./RunStatusBar";

const registeredNodeIds = ["load_sop", "check_steps", "summarize_result"];

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

describe("RunStatusBar", () => {
  it("displays status, subject type, and subject id", () => {
    render(<RunStatusBar summary={summary()} />);

    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("sop")).toBeInTheDocument();
    expect(screen.getByText("payment-release")).toBeInTheDocument();
  });

  it("does not display env_key", () => {
    const summaryWithEnv = {
      ...summary(),
      env_key: "production",
    } as RunSummary & { env_key: string };

    render(<RunStatusBar summary={summaryWithEnv} />);

    expect(screen.queryByText("production")).not.toBeInTheDocument();
    expect(screen.queryByText("env_key")).not.toBeInTheDocument();
  });
});

describe("RunNodeList", () => {
  it("renders known nodes in registry order and unknown nodes by first event sequence", () => {
    const state = stateFromEvents([
      event({ node: "custom_lint", sequence: 1 }),
      event({ node: "summarize_result", sequence: 2 }),
      event({ node: "check_steps", sequence: 3 }),
      event({ node: "early_custom", sequence: 0 }),
      event({ node: "load_sop", sequence: 4 }),
    ]);

    render(
      <RunNodeList state={state} registeredNodeIds={registeredNodeIds} />,
    );

    const nodeItems = screen.getAllByRole("listitem").map((item) => {
      const nodeName = within(item).getByTestId("run-node-id");

      return nodeName.textContent;
    });

    expect(nodeItems).toEqual([
      "load_sop",
      "check_steps",
      "summarize_result",
      "early_custom",
      "custom_lint",
    ]);
  });
});

describe("RunEventStream", () => {
  it("renders accumulated node stream text as markdown", () => {
    const state = stateFromEvents([
      event({
        type: "messages",
        node: "check_steps",
        sequence: 1,
        payload: { delta: "**checking** " },
      }),
      event({
        type: "messages",
        node: "check_steps",
        sequence: 2,
        payload: { delta: "steps" },
      }),
    ]);

    render(<RunEventStream state={state} />);

    const eventRegion = screen.getByLabelText("Run events");

    expect(within(eventRegion).getByText("checking")).toBeInTheDocument();
    expect(within(eventRegion).getByText("steps")).toBeInTheDocument();
    expect(within(eventRegion).getByTestId("stream-markdown")).toHaveTextContent(
      "checking steps",
    );
  });

  it("renders custom progress as a concise row", () => {
    const state = stateFromEvents([
      event({
        type: "custom",
        node: "check_steps",
        sequence: 1,
        payload: { progress: "Validated 3 of 5 steps" },
      }),
    ]);

    render(<RunEventStream state={state} />);

    expect(screen.getByText("Validated 3 of 5 steps")).toBeInTheDocument();
    expect(screen.queryByText("Details")).not.toBeInTheDocument();
  });

  it("renders object custom progress as a concise row", () => {
    const state = stateFromEvents([
      event({
        type: "custom",
        node: "check_steps",
        sequence: 1,
        payload: { progress: { current: 2, total: 3 } },
      }),
    ]);

    render(<RunEventStream state={state} />);

    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    expect(screen.queryByText(/\"current\"/)).not.toBeInTheDocument();
  });

  it("renders updates as expandable structured output", () => {
    const state = stateFromEvents([
      event({
        type: "updates",
        node: "summarize_result",
        sequence: 1,
        payload: { value: { score: 92 } },
      }),
    ]);

    render(<RunEventStream state={state} />);

    const details = screen.getByText("Details").closest("details");

    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText(/\"score\": 92/)).toBeInTheDocument();
  });

  it("renders errors as visible failure rows", () => {
    const state = stateFromEvents([
      event({
        type: "error",
        node: "check_steps",
        sequence: 1,
        payload: { message: "Quality check failed" },
      }),
    ]);

    render(<RunEventStream state={state} />);

    expect(screen.getByText("Quality check failed")).toBeInTheDocument();
  });

  it("renders checkpoints collapsed by default", () => {
    const state = stateFromEvents([
      event({
        type: "checkpoints",
        node: "check_steps",
        sequence: 1,
        payload: { checkpoint_id: "cp-1" },
      }),
    ]);

    render(<RunEventStream state={state} />);

    const details = screen.getByText("Details").closest("details");

    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText(/checkpoint_id/)).toBeInTheDocument();
  });
});

describe("RunObserver", () => {
  it("subscribes by run id and shows reconnecting without clearing previous events", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(summary({ latest_sequence: 0 })));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <RunObserver
        runId="run-1"
        registeredNodeIds={registeredNodeIds}
      />,
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/runs/run-1", expect.any(Object));
    expect(MockEventSource.instances[0]?.url).toBe(
      "/api/runs/run-1/events?after=0",
    );

    act(() => {
      MockEventSource.instances[0]?.emit(
        event({
          type: "messages",
          node: "check_steps",
          sequence: 1,
          payload: { delta: "Previously streamed text" },
        }),
        "1",
      );
      MockEventSource.instances[0]?.fail();
    });

    expect(screen.getByText("reconnecting")).toBeInTheDocument();
    expect(screen.getByLabelText("Run events")).toHaveTextContent(
      "Previously streamed text",
    );
  });
});

function summary(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    subject_type: "sop",
    subject_id: "payment-release",
    status: "running",
    current_node: "check_steps",
    completed_nodes: ["load_sop"],
    latest_sequence: 12,
    started_at: "2026-05-25T10:00:00Z",
    finished_at: null,
    result_status: null,
    error_summary: null,
    ...overrides,
  };
}

function stateFromEvents(events: RunEvent[]): RunViewState {
  return events.reduce(reduceRunEvent, createInitialRunViewState());
}

function event(overrides: Partial<RunEvent>): RunEvent {
  return {
    type: "tasks",
    node: "load_sop",
    thread_id: "quality-run:run-1",
    run_id: "run-1",
    sequence: 1,
    payload: { status: "started" },
    ...overrides,
  };
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

class MockEventSource {
  static instances: MockEventSource[] = [];

  private readonly listeners = new Map<string, Set<EventListener>>();

  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  closed = false;

  constructor(public readonly url: string) {
    MockEventSource.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }

  addEventListener(type: string, listener: EventListener): void {
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: EventListener): void {
    this.listeners.get(type)?.delete(listener);
  }

  emit(runEvent: RunEvent, lastEventId = ""): void {
    this.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify(runEvent),
        lastEventId,
      }),
    );
  }

  fail(): void {
    this.onerror?.(new Event("error"));
  }
}

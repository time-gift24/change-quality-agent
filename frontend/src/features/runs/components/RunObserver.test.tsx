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
import { RunObserver, RunObserverView } from "./RunObserver";

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

describe("RunObserverView", () => {
  it("renders a human prompt for the SOP subject", () => {
    const state = stateFromEvents([]);

    render(
      <RunObserverView
        summary={summary()}
        state={state}
        registeredNodeIds={registeredNodeIds}
      />,
    );

    expect(
      screen.getByText(/请对 SOP `payment-release` 执行一次质量检查。/),
    ).toBeInTheDocument();
  });

  it("renders each node's streamText as an assistant turn in registered order", () => {
    const state = stateFromEvents([
      event({
        type: "messages",
        node: "summarize_result",
        sequence: 1,
        payload: { delta: "all clear" },
      }),
      event({
        type: "messages",
        node: "load_sop",
        sequence: 2,
        payload: { delta: "loaded" },
      }),
    ]);

    render(
      <RunObserverView
        summary={summary()}
        state={state}
        registeredNodeIds={registeredNodeIds}
      />,
    );

    const turns = screen.getAllByLabelText(/Assistant turn /);

    expect(turns.map((turn) => turn.getAttribute("aria-label"))).toEqual([
      "Assistant turn load_sop",
      "Assistant turn summarize_result",
    ]);
    expect(within(turns[0]).getByTestId("stream-markdown")).toHaveTextContent(
      "loaded",
    );
    expect(within(turns[1]).getByTestId("stream-markdown")).toHaveTextContent(
      "all clear",
    );
  });

  it("shows a typing indicator while the node is streaming with no text yet", () => {
    const state = stateFromEvents([
      event({
        type: "tasks",
        node: "load_sop",
        sequence: 1,
        payload: { status: "started" },
      }),
    ]);

    render(
      <RunObserverView
        summary={summary({ status: "running" })}
        state={{ ...state, isRunning: true }}
        registeredNodeIds={registeredNodeIds}
      />,
    );

    const turn = screen.getByLabelText("Assistant turn load_sop");
    expect(within(turn).getByLabelText("streaming")).toBeInTheDocument();
  });

  it("renders node-level errors inline in the assistant turn", () => {
    const state = stateFromEvents([
      event({
        type: "messages",
        node: "load_sop",
        sequence: 1,
        payload: { delta: "Loading from upstream..." },
      }),
      event({
        type: "tasks",
        node: "load_sop",
        sequence: 2,
        payload: { status: "failed", error: "SOP upstream returned 502." },
      }),
    ]);

    render(
      <RunObserverView
        summary={summary({ status: "error" })}
        state={state}
        registeredNodeIds={registeredNodeIds}
      />,
    );

    const turn = screen.getByLabelText("Assistant turn load_sop");
    expect(
      within(turn).getByText("SOP upstream returned 502."),
    ).toBeInTheDocument();
    expect(within(turn).getByText("失败")).toBeInTheDocument();
  });

  it("renders run-level error_summary as a separate assistant error turn", () => {
    render(
      <RunObserverView
        summary={summary({ status: "error", error_summary: "graph aborted" })}
        state={stateFromEvents([])}
        registeredNodeIds={registeredNodeIds}
      />,
    );

    const errorTurn = screen.getByLabelText("Assistant turn error");
    expect(within(errorTurn).getByText("graph aborted")).toBeInTheDocument();
  });
});

describe("RunObserver", () => {
  it("subscribes by run id and keeps streamed text across reconnect", async () => {
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

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1",
      expect.any(Object),
    );
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

    expect(
      screen.getByTestId("stream-markdown"),
    ).toHaveTextContent("Previously streamed text");
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

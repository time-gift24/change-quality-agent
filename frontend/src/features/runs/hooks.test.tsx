// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRun, useRunEvents } from "./hooks";
import type { RunEvent, RunSummary } from "./types";

describe("run SSE hooks", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("connects with after=latestSequence", async () => {
    renderHook(() => useRunEvents("run-1", 12));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    expect(MockEventSource.instances[0]?.url).toBe(
      "/api/runs/run-1/events?after=12",
    );
  });

  it("updates local cursor from event id or event sequence", async () => {
    const { result } = renderHook(() => useRunEvents("run-1", 0));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emit(event({ sequence: 2 }), "5");
      MockEventSource.instances[0]?.fail();
    });

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(2);
    });
    expect(MockEventSource.instances[1]?.url).toBe(
      "/api/runs/run-1/events?after=5",
    );
    expect(result.current.latestSequence).toBe(2);

    act(() => {
      MockEventSource.instances[1]?.emit(event({ sequence: 9 }));
      MockEventSource.instances[1]?.fail();
    });

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(3);
    });
    expect(MockEventSource.instances[2]?.url).toBe(
      "/api/runs/run-1/events?after=9",
    );
  });

  it("ignores heartbeat comments", async () => {
    const { result } = renderHook(() => useRunEvents("run-1", 0));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.comment();
    });

    expect(result.current.events).toEqual([]);
    expect(result.current.latestSequence).toBe(0);
  });

  it("reconnect keeps prior events", async () => {
    const { result } = renderHook(() => useRunEvents("run-1", 0));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emit(event({ sequence: 1 }));
      MockEventSource.instances[0]?.fail();
    });

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(2);
    });

    act(() => {
      MockEventSource.instances[1]?.emit(
        event({ sequence: 2, payload: { delta: "after reconnect" } }),
      );
    });

    expect(result.current.events.map((item) => item.sequence)).toEqual([1, 2]);
  });

  it("terminal done closes stream and triggers summary refresh", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(summary({ latest_sequence: 2 })))
      .mockResolvedValueOnce(
        jsonResponse(summary({ status: "success", latest_sequence: 3 })),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRun("run-1"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    expect(MockEventSource.instances[0]?.url).toBe(
      "/api/runs/run-1/events?after=2",
    );

    act(() => {
      MockEventSource.instances[0]?.emit(
        event({ type: "done", node: null, sequence: 3 }),
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    expect(MockEventSource.instances[0]?.closed).toBe(true);
    expect(result.current.summary?.status).toBe("success");
    expect(result.current.events.isRunning).toBe(false);
  });

  it("terminal error closes stream and triggers summary refresh", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(summary({ latest_sequence: 4 })))
      .mockResolvedValueOnce(
        jsonResponse(summary({ status: "error", latest_sequence: 5 })),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useRun("run-1"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emit(
        event({
          type: "error",
          node: "check_steps",
          sequence: 5,
          payload: { message: "failed" },
        }),
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    expect(MockEventSource.instances[0]?.closed).toBe(true);
  });
});

class MockEventSource {
  static instances: MockEventSource[] = [];

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

  comment(): void {
    this.onopen?.(new Event("open"));
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

function event(overrides: Partial<RunEvent>): RunEvent {
  return {
    type: "messages",
    node: "check_steps",
    thread_id: "quality-run:run-1",
    run_id: "run-1",
    sequence: 1,
    payload: { delta: "chunk" },
    ...overrides,
  };
}

function summary(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    subject_type: "sop",
    subject_id: "payment-release",
    status: "running",
    current_node: "check_steps",
    completed_nodes: ["load_sop"],
    latest_sequence: 1,
    ...overrides,
  };
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

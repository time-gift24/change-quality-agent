// @vitest-environment jsdom

import { act, render, renderHook, waitFor } from "@testing-library/react";
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

    vi.useFakeTimers();

    act(() => {
      MockEventSource.instances[0]?.emit(event({ sequence: 2 }), "5");
      MockEventSource.instances[0]?.fail();
      vi.advanceTimersByTime(1_000);
    });

    expect(MockEventSource.instances).toHaveLength(2);
    expect(MockEventSource.instances[1]?.url).toBe(
      "/api/runs/run-1/events?after=5",
    );
    expect(result.current.latestSequence).toBe(2);

    act(() => {
      MockEventSource.instances[1]?.emit(event({ sequence: 9 }));
      MockEventSource.instances[1]?.fail();
      vi.advanceTimersByTime(1_000);
    });

    expect(MockEventSource.instances).toHaveLength(3);
    expect(MockEventSource.instances[2]?.url).toBe(
      "/api/runs/run-1/events?after=9",
    );
  });

  it("reduces named SSE event frames", async () => {
    const { result } = renderHook(() => useRunEvents("run-1", 0));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emitNamed(
        event({
          sequence: 2,
          payload: { delta: "named frame" },
        }),
        "2",
      );
    });

    expect(result.current.events.map((item) => item.sequence)).toEqual([2]);
    expect(result.current.nodes.check_steps?.streamText).toBe("named frame");
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

    vi.useFakeTimers();

    act(() => {
      MockEventSource.instances[0]?.emit(event({ sequence: 1 }));
      MockEventSource.instances[0]?.fail();
      vi.advanceTimersByTime(1_000);
    });

    expect(MockEventSource.instances).toHaveLength(2);

    act(() => {
      MockEventSource.instances[1]?.emit(
        event({ sequence: 2, payload: { delta: "after reconnect" } }),
      );
    });

    expect(result.current.events.map((item) => item.sequence)).toEqual([1, 2]);
  });

  it("paces reconnect attempts when the stream errors", async () => {
    const { result } = renderHook(() => useRunEvents("run-1", 0));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    vi.useFakeTimers();

    act(() => {
      MockEventSource.instances[0]?.fail();
    });

    expect(result.current.connectionStatus).toBe("reconnecting");
    expect(MockEventSource.instances).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(999);
    });

    expect(MockEventSource.instances).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(MockEventSource.instances).toHaveLength(2);
  });

  it("resets stream state when disabled", async () => {
    const { result, rerender } = renderHook(
      ({ enabled }) => useRunEvents("run-1", 0, { enabled }),
      {
        initialProps: { enabled: true },
      },
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emit(event({ sequence: 1 }));
    });

    expect(result.current.events).toHaveLength(1);

    rerender({ enabled: false });

    expect(result.current.events).toEqual([]);
    expect(result.current.latestSequence).toBe(0);
    expect(result.current.connectionStatus).toBe("idle");
  });

  it("does not expose stale stream state during the disabled render", async () => {
    const snapshots: RunViewSnapshot[] = [];

    function Capture({ enabled }: { enabled: boolean }) {
      snapshots.push(useRunEvents("run-1", 0, { enabled }));
      return null;
    }

    const { rerender } = render(<Capture enabled />);

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emit(event({ sequence: 1 }));
    });

    snapshots.length = 0;
    rerender(<Capture enabled={false} />);

    expect(snapshots[0]?.events).toEqual([]);
    expect(snapshots[0]?.connectionStatus).toBe("idle");
  });

  it("ignores stale summary responses after runId changes", async () => {
    const requests: Array<Deferred<Response>> = [];
    const fetchMock = vi.fn(() => {
      const request = deferred<Response>();
      requests.push(request);
      return request.promise;
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result, rerender } = renderHook(
      ({ runId }) => useRun(runId),
      {
        initialProps: { runId: "run-a" },
      },
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/runs/run-a",
        expect.any(Object),
      );
    });

    rerender({ runId: "run-b" });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/runs/run-b",
        expect.any(Object),
      );
    });

    await act(async () => {
      requests[1]?.resolve(
        jsonResponse(summary({ run_id: "run-b", latest_sequence: 7 })),
      );
    });

    await waitFor(() => {
      expect(result.current.summary?.run_id).toBe("run-b");
    });

    await act(async () => {
      requests[0]?.resolve(
        jsonResponse(summary({ run_id: "run-a", latest_sequence: 3 })),
      );
    });

    expect(result.current.summary?.run_id).toBe("run-b");
    expect(result.current.events.latestSequence).toBe(7);
  });

  it("does not expose stale run data during the runId switch render", async () => {
    const requests: Array<Deferred<Response>> = [];
    const snapshots: UseRunSnapshot[] = [];
    const fetchMock = vi.fn(() => {
      const request = deferred<Response>();
      requests.push(request);
      return request.promise;
    });
    vi.stubGlobal("fetch", fetchMock);

    function Capture({ runId }: { runId: string }) {
      snapshots.push(useRun(runId));
      return null;
    }

    const { rerender } = render(<Capture runId="run-a" />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/runs/run-a",
        expect.any(Object),
      );
    });

    await act(async () => {
      requests[0]?.resolve(
        jsonResponse(summary({ run_id: "run-a", latest_sequence: 7 })),
      );
    });

    await waitFor(() => {
      expect(snapshots.at(-1)?.summary?.run_id).toBe("run-a");
    });

    act(() => {
      MockEventSource.instances[0]?.emit(event({ sequence: 8 }));
    });

    snapshots.length = 0;
    rerender(<Capture runId="run-b" />);

    expect(snapshots[0]?.summary).toBeNull();
    expect(snapshots[0]?.summaryLoading).toBe(true);
    expect(snapshots[0]?.events.events).toEqual([]);
    expect(snapshots[0]?.events.latestSequence).toBe(0);
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
    await waitFor(() => {
      expect(result.current.summary?.status).toBe("success");
    });
    expect(result.current.events.isRunning).toBe(false);
  });

  it("terminal named done closes stream and triggers summary refresh", async () => {
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

    act(() => {
      MockEventSource.instances[0]?.emitNamed(
        event({ type: "done", node: null, sequence: 3 }),
        "3",
      );
    });

    await waitFor(() => {
      expect(result.current.summary?.status).toBe("success");
    });
    expect(MockEventSource.instances[0]?.closed).toBe(true);
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

  it("terminal named error closes stream instead of reconnecting", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(summary({ latest_sequence: 4 })))
      .mockResolvedValueOnce(
        jsonResponse(summary({ status: "error", latest_sequence: 5 })),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRun("run-1"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    vi.useFakeTimers();

    await act(async () => {
      MockEventSource.instances[0]?.emitNamed(
        event({
          type: "error",
          node: "check_steps",
          sequence: 5,
          payload: { message: "failed" },
        }),
        "5",
      );
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.summary?.status).toBe("error");
    expect(MockEventSource.instances[0]?.closed).toBe(true);

    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    expect(MockEventSource.instances).toHaveLength(1);
    expect(result.current.events.connectionStatus).toBe("closed");
  });
});

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

  emitNamed(runEvent: RunEvent, lastEventId = ""): void {
    const message = new MessageEvent(runEvent.type, {
      data: JSON.stringify(runEvent),
      lastEventId,
    });

    for (const listener of this.listeners.get(runEvent.type) ?? []) {
      listener(message);
    }

    if (runEvent.type === "error") {
      this.onerror?.(message);
    }
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

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

type UseRunSnapshot = ReturnType<typeof useRun>;
type RunViewSnapshot = ReturnType<typeof useRunEvents>;

function deferred<T>(): Deferred<T> {
  let resolve: (value: T) => void = () => {};
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });

  return { promise, resolve };
}

// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHECK_EVENT_NAMES, useSopQualityCheck } from "./hooks";
import type { SopQualityCheckDetail, SopQualityCheckEvent } from "./types";

describe("sop quality check hooks", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("connects with after=display latest sequence", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(detail({ latest_sequence: 12 }))),
    );

    renderHook(() => useSopQualityCheck("check-1"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    expect(MockEventSource.instances[0]?.url).toBe(
      "/api/sop-quality-checks/check-1/stream?after=12",
    );
  });

  it("refreshes detail when a checkpoint event arrives", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail({ latest_sequence: 0 })))
      .mockResolvedValueOnce(jsonResponse(detail({ latest_sequence: 2 })));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSopQualityCheck("check-1"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emitNamed(
        event({ type: "checkpoint", sequence: 2 }),
        "2",
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    expect(result.current.state.latestSequence).toBe(2);
  });

  it("subscribes to streamed message events", () => {
    expect(CHECK_EVENT_NAMES).toContain("messages");
  });

  it("opens the session stream when detail has session_id", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/sop-quality-checks/check-1") {
        return Promise.resolve(
          jsonResponse(detail({ session_id: 42, latest_sequence: 5 })),
        );
      }
      if (url === "/api/sessions/42/messages?after=0") {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse({}));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useSopQualityCheck("check-1"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    expect(MockEventSource.instances[0]?.url).toMatch(
      /^\/api\/sessions\/42\/stream\?after=/,
    );
  });

  it("ignores stale detail after check id changes", async () => {
    const requests: Array<Deferred<Response>> = [];
    const fetchMock = vi.fn(() => {
      const request = deferred<Response>();
      requests.push(request);
      return request.promise;
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result, rerender } = renderHook(
      ({ checkId }) => useSopQualityCheck(checkId),
      { initialProps: { checkId: "check-a" } },
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sop-quality-checks/check-a",
        expect.any(Object),
      );
    });

    rerender({ checkId: "check-b" });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sop-quality-checks/check-b",
        expect.any(Object),
      );
    });

    await act(async () => {
      requests[1]?.resolve(jsonResponse(detail({ check_id: "check-b" })));
    });

    await waitFor(() => {
      expect(result.current.detail?.check_id).toBe("check-b");
    });

    await act(async () => {
      requests[0]?.resolve(jsonResponse(detail({ check_id: "check-a" })));
    });

    expect(result.current.detail?.check_id).toBe("check-b");
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

  emitNamed(checkEvent: SopQualityCheckEvent, lastEventId = ""): void {
    const message = new MessageEvent(checkEvent.type, {
      data: JSON.stringify(checkEvent),
      lastEventId,
    });

    for (const listener of this.listeners.get(checkEvent.type) ?? []) {
      listener(message);
    }
  }
}

function event(
  overrides: Partial<SopQualityCheckEvent> = {},
): SopQualityCheckEvent {
  return {
    check_id: "check-1",
    sequence: 1,
    type: "checkpoint",
    node: "review_sop",
    checkpoint_id: "checkpoint-1",
    task_id: null,
    message: "Checkpoint saved.",
    ...overrides,
  };
}

function detail(
  overrides: Partial<SopQualityCheckDetail> = {},
): SopQualityCheckDetail {
  return {
    check_id: "check-1",
    sop_id: "release-checklist",
    env_key: "dev",
    status: "running",
    latest_sequence: 0,
    current_checkpoint_id: null,
    result: null,
    error: null,
    display_state: {
      latest_sequence: overrides.latest_sequence ?? 0,
      nodes: {},
      is_running: true,
    },
    session_id: null,
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

function deferred<T>(): Deferred<T> {
  let resolve: (value: T) => void = () => {};
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });

  return { promise, resolve };
}

// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStream } from "./hooks";

describe("session stream hook", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("hydrates from persisted messages then opens SSE", async () => {
    const messages = [
      {
        id: "msg-1",
        session_id: 1,
        sequence: 3,
        role: "assistant",
        content: "existing",
        additional_kwargs: {},
        created_at: "",
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(messages), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const { result } = renderHook(() => useSessionStream(1));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    expect(MockEventSource.instances[0]?.url).toBe(
      "/api/sessions/1/stream?after=3",
    );

    await waitFor(() => {
      expect(result.current.state.messages).toHaveLength(1);
    });
    expect(result.current.state.latestSequence).toBe(3);
    expect(result.current.loading).toBe(false);
  });

  it("returns idle state when sessionId is null", () => {
    const { result } = renderHook(() => useSessionStream(null));

    expect(result.current.state.connectionStatus).toBe("idle");
    expect(result.current.loading).toBe(false);
  });

  it("processes live message_delta then final message event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const { result } = renderHook(() => useSessionStream(1));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emitNamed({
        type: "message_delta",
        session_id: 1,
        sequence: null,
        role: "assistant",
        content: "streaming...",
        additional_kwargs: { step: "review_sop" },
      });
    });

    expect(result.current.state.liveBuffers["step:review_sop"]).toBe(
      "streaming...",
    );

    act(() => {
      MockEventSource.instances[0]?.emitNamed({
        type: "message",
        session_id: 1,
        sequence: 5,
        role: "assistant",
        content: "final text",
        additional_kwargs: { step: "review_sop" },
      });
    });

    await waitFor(() => {
      expect(result.current.state.messages).toHaveLength(1);
    });
    expect(result.current.state.liveBuffers["step:review_sop"]).toBeUndefined();
    expect(result.current.state.latestSequence).toBe(5);
  });

  it("processes backend persisted message envelope events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const { result } = renderHook(() => useSessionStream(1));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    act(() => {
      MockEventSource.instances[0]?.emitNamed({
        type: "message",
        message: {
          id: "msg-7",
          session_id: 1,
          sequence: 7,
          role: "assistant",
          content: "final text",
          additional_kwargs: { step: "review_sop" },
          created_at: "",
        },
      });
    });

    await waitFor(() => {
      expect(result.current.state.messages).toHaveLength(1);
    });
    expect(result.current.state.messages[0]?.id).toBe("msg-7");
    expect(result.current.state.latestSequence).toBe(7);
  });

  it("closes without reconnecting when a terminal event arrives", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const { result } = renderHook(() => useSessionStream(1));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    vi.useFakeTimers();

    act(() => {
      MockEventSource.instances[0]?.emitNamed({
        type: "completed",
        session_id: 1,
      });
    });

    expect(result.current.state.connectionStatus).toBe("closed");
    expect(MockEventSource.instances[0]?.closed).toBe(true);

    act(() => {
      MockEventSource.instances[0]?.onerror?.(new Event("error"));
      vi.runOnlyPendingTimers();
    });

    expect(MockEventSource.instances).toHaveLength(1);
  });

  it("sets error when fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network error")),
    );

    const { result } = renderHook(() => useSessionStream(1));

    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });

    expect(result.current.error?.message).toBe("network error");
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

  emitNamed(data: Record<string, unknown>): void {
    const eventType = data.type as string;
    const message = new MessageEvent(eventType, {
      data: JSON.stringify(data),
    });

    for (const listener of this.listeners.get(eventType) ?? []) {
      listener(message);
    }
  }
}

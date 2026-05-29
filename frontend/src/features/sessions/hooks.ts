import { useEffect, useRef, useState } from "react";

import { createSseEventSource } from "../../lib/sse";
import { buildSessionStreamUrl, getSessionMessages } from "./api";
import {
  createInitialSessionViewState,
  hydrateSessionViewState,
  reduceSessionStreamEvent,
  type SessionViewState,
} from "./reducer";
import type { SessionStreamEvent } from "./types";

const RECONNECT_DELAY_MS = 1_000;

export const SESSION_STREAM_EVENT_NAMES: SessionStreamEvent["type"][] = [
  "message",
  "message_delta",
];

export type UseSessionStreamResult = {
  state: SessionViewState;
  error: Error | null;
  loading: boolean;
};

export function useSessionStream(
  sessionId: number | null,
): UseSessionStreamResult {
  const cursorRef = useRef(0);
  const [state, setState] = useState<SessionViewState>(
    createInitialSessionViewState,
  );
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(sessionId !== null);
  const [hydratedFor, setHydratedFor] = useState<number | null>(null);

  useEffect(() => {
    cursorRef.current = 0;
    setError(null);
    setHydratedFor(null);
    setState(createInitialSessionViewState());

    if (sessionId === null) {
      setLoading(false);
      return;
    }

    setLoading(true);

    let cancelled = false;

    (async () => {
      try {
        const messages = await getSessionMessages(sessionId, 0);
        if (cancelled) {
          return;
        }
        const hydrated = hydrateSessionViewState(messages);
        cursorRef.current = hydrated.latestSequence;
        setState(hydrated);
        setHydratedFor(sessionId);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    if (sessionId === null || hydratedFor !== sessionId) {
      return;
    }

    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let isClosed = false;

    const connect = () => {
      if (isClosed) {
        return;
      }
      const source = createSseEventSource(
        buildSessionStreamUrl(sessionId, cursorRef.current),
      );
      eventSource = source;

      source.onopen = () => {
        setState((current) => ({ ...current, connectionStatus: "open" }));
      };

      const handle = (message: MessageEvent<string>) => {
        const event = parseSessionStreamEvent(message.data);
        if (!event) {
          return;
        }
        if (event.type === "message" && typeof event.sequence === "number") {
          cursorRef.current = Math.max(cursorRef.current, event.sequence);
        }
        setState((current) => reduceSessionStreamEvent(current, event));
      };

      source.onmessage = handle;
      for (const name of SESSION_STREAM_EVENT_NAMES) {
        source.addEventListener(name, (e: Event) => {
          if ("data" in e && typeof (e as MessageEvent).data === "string") {
            handle(e as MessageEvent<string>);
          }
        });
      }

      source.onerror = () => {
        source.close();
        eventSource = null;
        setState((current) => ({
          ...current,
          connectionStatus: "reconnecting",
        }));
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, RECONNECT_DELAY_MS);
      };
    };

    setState((current) => ({ ...current, connectionStatus: "connecting" }));
    connect();

    return () => {
      isClosed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      eventSource?.close();
    };
  }, [sessionId, hydratedFor]);

  return { state, error, loading };
}

function parseSessionStreamEvent(data: string): SessionStreamEvent | null {
  if (!data.trim()) {
    return null;
  }
  try {
    const parsed = normalizeSessionStreamEvent(JSON.parse(data));
    if (parsed.type !== "message" && parsed.type !== "message_delta") {
      return null;
    }
    if (typeof parsed.session_id !== "number") {
      return null;
    }
    return parsed as SessionStreamEvent;
  } catch {
    return null;
  }
}

function normalizeSessionStreamEvent(parsed: unknown): Partial<SessionStreamEvent> {
  if (
    parsed !== null &&
    typeof parsed === "object" &&
    "type" in parsed &&
    (parsed as { type?: unknown }).type === "message" &&
    "message" in parsed &&
    typeof (parsed as { message?: unknown }).message === "object" &&
    (parsed as { message?: unknown }).message !== null
  ) {
    return {
      type: "message",
      ...((parsed as { message: Record<string, unknown> }).message),
    } as Partial<SessionStreamEvent>;
  }
  return parsed as Partial<SessionStreamEvent>;
}

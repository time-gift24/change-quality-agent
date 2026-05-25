import { useCallback, useEffect, useRef, useState } from "react";

import { createRunEventSource } from "../../lib/sse";
import { buildRunEventsUrl, getRun } from "./api";
import {
  createInitialRunViewState,
  reduceRunEvent,
  type RunViewState,
} from "./reducer";
import type { RunEvent, RunSummary } from "./types";

const RECONNECT_DELAY_MS = 1_000;

type UseRunEventsOptions = {
  enabled?: boolean;
  onTerminal?: () => void;
};

export type UseRunResult = {
  summary: RunSummary | null;
  summaryError: Error | null;
  summaryLoading: boolean;
  refreshSummary: () => Promise<void>;
  events: RunViewState;
};

export function useRun(runId: string): UseRunResult {
  const activeRunIdRef = useRef(runId);
  const summaryRequestRef = useRef(0);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [eventsInitialAfter, setEventsInitialAfter] = useState<
    number | undefined
  >();
  const [summaryError, setSummaryError] = useState<Error | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  activeRunIdRef.current = runId;

  const refreshSummary = useCallback(async () => {
    const requestId = summaryRequestRef.current + 1;
    const requestedRunId = runId;

    summaryRequestRef.current = requestId;
    setSummaryLoading(true);
    setSummaryError(null);

    try {
      const nextSummary = await getRun(requestedRunId);

      if (
        summaryRequestRef.current !== requestId ||
        activeRunIdRef.current !== requestedRunId
      ) {
        return;
      }

      setSummary(nextSummary);
      setEventsInitialAfter((current) =>
        current === undefined ? nextSummary.latest_sequence : current,
      );
    } catch (error) {
      if (
        summaryRequestRef.current !== requestId ||
        activeRunIdRef.current !== requestedRunId
      ) {
        return;
      }

      setSummaryError(asError(error));
    } finally {
      if (
        summaryRequestRef.current !== requestId ||
        activeRunIdRef.current !== requestedRunId
      ) {
        return;
      }

      setSummaryLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    setSummary(null);
    setEventsInitialAfter(undefined);
    setSummaryLoading(true);
  }, [runId]);

  useEffect(() => {
    void refreshSummary();
  }, [refreshSummary]);

  const events = useRunEvents(runId, eventsInitialAfter, {
    enabled:
      summary?.run_id === runId && eventsInitialAfter !== undefined,
    onTerminal: () => {
      void refreshSummary();
    },
  });

  return {
    summary,
    summaryError,
    summaryLoading,
    refreshSummary,
    events,
  };
}

export function useRunEvents(
  runId: string,
  initialAfter?: number,
  options: UseRunEventsOptions = {},
): RunViewState {
  const { enabled = true, onTerminal } = options;
  const onTerminalRef = useRef(onTerminal);
  const [state, setState] = useState<RunViewState>(() =>
    initialState(initialAfter),
  );

  onTerminalRef.current = onTerminal;

  useEffect(() => {
    if (!enabled) {
      setState(initialState(initialAfter));
      return;
    }

    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let isClosed = false;
    let isTerminal = false;
    const cursorRef = { current: initialAfter ?? 0 };

    setState({
      ...initialState(initialAfter),
      connectionStatus: "connecting",
    });

    const closeCurrentSource = () => {
      eventSource?.close();
      eventSource = null;
    };

    const connect = () => {
      if (isClosed || isTerminal) {
        return;
      }

      const source = createRunEventSource(
        buildRunEventsUrl(runId, cursorRef.current),
      );
      eventSource = source;

      source.onopen = () => {
        setState((current) => ({
          ...current,
          connectionStatus: "open",
        }));
      };

      source.onmessage = (message) => {
        const event = parseRunEvent(message.data);

        if (!event) {
          return;
        }

        cursorRef.current = nextCursor(cursorRef.current, message, event);

        setState((current) => reduceRunEvent(current, event));

        if (event.type === "done" || event.type === "error") {
          isTerminal = true;
          closeCurrentSource();
          onTerminalRef.current?.();
        }
      };

      source.onerror = () => {
        if (isClosed || isTerminal) {
          return;
        }

        closeCurrentSource();
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

    connect();

    return () => {
      isClosed = true;

      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }

      closeCurrentSource();
    };
  }, [enabled, initialAfter, runId]);

  return state;
}

function initialState(initialAfter?: number): RunViewState {
  return {
    ...createInitialRunViewState(),
    latestSequence: initialAfter ?? 0,
  };
}

function parseRunEvent(data: string): RunEvent | null {
  if (!data.trim()) {
    return null;
  }

  try {
    return JSON.parse(data) as RunEvent;
  } catch {
    return null;
  }
}

function nextCursor(
  current: number,
  message: MessageEvent<string>,
  event: RunEvent,
): number {
  const eventId = Number.parseInt(message.lastEventId, 10);

  if (Number.isFinite(eventId)) {
    return Math.max(current, eventId);
  }

  return Math.max(current, event.sequence);
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

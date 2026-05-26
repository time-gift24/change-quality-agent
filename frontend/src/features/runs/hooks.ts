import { useCallback, useEffect, useRef, useState } from "react";

import { createRunEventSource } from "../../lib/sse";
import { buildRunEventsUrl, getRun } from "./api";
import {
  createInitialRunViewState,
  reduceRunEvent,
  type RunViewState,
} from "./reducer";
import type { RunEvent, RunStatus, RunSummary } from "./types";

const RECONNECT_DELAY_MS = 1_000;
const TERMINAL_RUN_STATUSES: RunStatus[] = [
  "success",
  "error",
  "timeout",
  "interrupted",
];
const RUN_EVENT_NAMES: RunEvent["type"][] = [
  "tasks",
  "messages",
  "updates",
  "custom",
  "checkpoints",
  "done",
  "error",
];

type UseRunEventsOptions = {
  enabled?: boolean;
  summaryIsTerminal?: boolean;
  onTerminal?: () => void;
};

type SummaryErrorState = {
  runId: string;
  error: Error;
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
  const [summaryError, setSummaryError] = useState<SummaryErrorState | null>(
    null,
  );
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
      setEventsInitialAfter((current) => (current === undefined ? 0 : current));
    } catch (error) {
      if (
        summaryRequestRef.current !== requestId ||
        activeRunIdRef.current !== requestedRunId
      ) {
        return;
      }

      setSummaryError({
        runId: requestedRunId,
        error: asError(error),
      });
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
    setSummaryError(null);
    setSummaryLoading(true);
  }, [runId]);

  useEffect(() => {
    void refreshSummary();
  }, [refreshSummary]);

  const visibleSummary = summary?.run_id === runId ? summary : null;
  const visibleSummaryError =
    summaryError?.runId === runId ? summaryError.error : null;
  const streamInitialAfter =
    visibleSummary && eventsInitialAfter !== undefined
      ? eventsInitialAfter
      : undefined;
  const streamEnabled =
    visibleSummary !== null && streamInitialAfter !== undefined;
  const summaryIsTerminal =
    visibleSummary !== null &&
    TERMINAL_RUN_STATUSES.includes(visibleSummary.status);
  const events = useRunEvents(runId, streamInitialAfter, {
    enabled: streamEnabled,
    summaryIsTerminal,
    onTerminal: () => {
      void refreshSummary();
    },
  });

  return {
    summary: visibleSummary,
    summaryError: visibleSummaryError,
    summaryLoading:
      summaryLoading ||
      (visibleSummary === null && visibleSummaryError === null),
    refreshSummary,
    events,
  };
}

export function useRunEvents(
  runId: string,
  initialAfter?: number,
  options: UseRunEventsOptions = {},
): RunViewState {
  const { enabled = true, summaryIsTerminal = false, onTerminal } = options;
  const onTerminalRef = useRef(onTerminal);
  const summaryIsTerminalRef = useRef(summaryIsTerminal);
  const [state, setState] = useState<RunViewState>(() =>
    initialState(initialAfter),
  );

  onTerminalRef.current = onTerminal;
  summaryIsTerminalRef.current = summaryIsTerminal;

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

    const isCurrentSource = (source: EventSource) =>
      !isClosed && !isTerminal && eventSource === source;

    const connect = () => {
      if (isClosed || isTerminal) {
        return;
      }

      const source = createRunEventSource(
        buildRunEventsUrl(runId, cursorRef.current),
      );
      eventSource = source;

      source.onopen = () => {
        if (!isCurrentSource(source)) {
          return;
        }

        setState((current) => ({
          ...current,
          connectionStatus: "open",
        }));
      };

      const handleRunMessage = (message: MessageEvent<string>) => {
        if (!isCurrentSource(source)) {
          return;
        }

        const event = parseRunEvent(message.data);

        if (!event) {
          return;
        }

        cursorRef.current = nextCursor(cursorRef.current, message, event);

        setState((current) => reduceRunEvent(current, event));

        if (event.type === "done" || event.type === "error") {
          isTerminal = true;
          source.close();
          eventSource = null;
          onTerminalRef.current?.();
        }
      };

      source.onmessage = handleRunMessage;

      const handleNamedRunEvent = (event: Event) => {
        if (isMessageEvent(event)) {
          handleRunMessage(event);
        }
      };

      for (const eventName of RUN_EVENT_NAMES) {
        source.addEventListener(eventName, handleNamedRunEvent);
      }

      source.onerror = (event) => {
        if (!isCurrentSource(source)) {
          return;
        }

        if (isMessageEvent(event)) {
          return;
        }

        source.close();
        eventSource = null;

        if (summaryIsTerminalRef.current) {
          isTerminal = true;
          setState((current) => ({
            ...current,
            connectionStatus: "closed",
          }));
          onTerminalRef.current?.();
          return;
        }

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

  if (!enabled) {
    return initialState(initialAfter);
  }

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

function isMessageEvent(event: Event): event is MessageEvent<string> {
  return (
    "data" in event &&
    typeof (event as MessageEvent<unknown>).data === "string"
  );
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

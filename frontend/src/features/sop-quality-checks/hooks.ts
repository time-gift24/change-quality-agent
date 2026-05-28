import { useCallback, useEffect, useRef, useState } from "react";

import { createSseEventSource } from "../../lib/sse";
import { buildSopQualityCheckStreamUrl, getSopQualityCheck } from "./api";
import {
  createInitialSopQualityCheckViewState,
  hydrateFromDisplayState,
  reduceSopQualityCheckEvent,
  type SopQualityCheckViewState,
} from "./reducer";
import type {
  SopQualityCheckDetail,
  SopQualityCheckEvent,
  SopQualityCheckStatus,
} from "./types";

const RECONNECT_DELAY_MS = 1_000;
const TERMINAL_CHECK_STATUSES: SopQualityCheckStatus[] = [
  "succeeded",
  "failed",
  "cancelled",
  "interrupted",
];
export const CHECK_EVENT_NAMES: SopQualityCheckEvent["type"][] = [
  "created",
  "started",
  "messages",
  "updates",
  "checkpoint",
  "completed",
  "failed",
  "interrupted",
];

type DetailErrorState = {
  checkId: string;
  error: Error;
};

export type UseSopQualityCheckResult = {
  detail: SopQualityCheckDetail | null;
  error: Error | null;
  loading: boolean;
  refreshDetail: () => Promise<void>;
  state: SopQualityCheckViewState;
};

export function useSopQualityCheck(checkId: string): UseSopQualityCheckResult {
  const activeCheckIdRef = useRef(checkId);
  const detailRequestRef = useRef(0);
  const cursorRef = useRef(0);
  const terminalRef = useRef(false);
  const [detail, setDetail] = useState<SopQualityCheckDetail | null>(null);
  const [detailError, setDetailError] = useState<DetailErrorState | null>(null);
  const [loading, setLoading] = useState(true);
  const [state, setState] = useState<SopQualityCheckViewState>(
    createInitialSopQualityCheckViewState,
  );

  activeCheckIdRef.current = checkId;

  const refreshDetail = useCallback(async () => {
    const requestId = detailRequestRef.current + 1;
    const requestedCheckId = checkId;

    detailRequestRef.current = requestId;
    setLoading(true);
    setDetailError(null);

    try {
      const nextDetail = await getSopQualityCheck(requestedCheckId);

      if (
        detailRequestRef.current !== requestId ||
        activeCheckIdRef.current !== requestedCheckId
      ) {
        return;
      }

      cursorRef.current = nextDetail.display_state.latest_sequence;
      terminalRef.current = TERMINAL_CHECK_STATUSES.includes(nextDetail.status);
      setDetail(nextDetail);
      setState({
        ...hydrateFromDisplayState(nextDetail.display_state),
        connectionStatus: terminalRef.current ? "closed" : "idle",
      });
    } catch (error) {
      if (
        detailRequestRef.current !== requestId ||
        activeCheckIdRef.current !== requestedCheckId
      ) {
        return;
      }

      setDetailError({ checkId: requestedCheckId, error: asError(error) });
    } finally {
      if (
        detailRequestRef.current !== requestId ||
        activeCheckIdRef.current !== requestedCheckId
      ) {
        return;
      }

      setLoading(false);
    }
  }, [checkId]);

  useEffect(() => {
    cursorRef.current = 0;
    terminalRef.current = false;
    setDetail(null);
    setDetailError(null);
    setLoading(true);
    setState(createInitialSopQualityCheckViewState());
  }, [checkId]);

  useEffect(() => {
    void refreshDetail();
  }, [refreshDetail]);

  useEffect(() => {
    if (detail === null || TERMINAL_CHECK_STATUSES.includes(detail.status)) {
      return;
    }

    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let isClosed = false;
    const streamCheckId = checkId;

    const closeCurrentSource = () => {
      eventSource?.close();
      eventSource = null;
    };

    const isCurrentSource = (source: EventSource) =>
      !isClosed && !terminalRef.current && eventSource === source;

    const connect = () => {
      if (isClosed || terminalRef.current) {
        return;
      }

      const source = createSseEventSource(
        buildSopQualityCheckStreamUrl(streamCheckId, cursorRef.current),
      );
      eventSource = source;

      source.onopen = () => {
        if (!isCurrentSource(source)) {
          return;
        }

        setState((current) => ({ ...current, connectionStatus: "open" }));
      };

      const handleCheckMessage = (message: MessageEvent<string>) => {
        if (!isCurrentSource(source)) {
          return;
        }

        const event = parseSopQualityCheckEvent(message.data);
        if (!event || event.check_id !== streamCheckId) {
          return;
        }

        cursorRef.current = nextCursor(cursorRef.current, message, event);
        setState((current) => reduceSopQualityCheckEvent(current, event));

        if (event.type === "checkpoint") {
          void refreshDetail();
        }

        if (isTerminalEvent(event)) {
          terminalRef.current = true;
          source.close();
          eventSource = null;
          void refreshDetail();
        }
      };

      source.onmessage = handleCheckMessage;

      const handleNamedCheckEvent = (event: Event) => {
        if (isMessageEvent(event)) {
          handleCheckMessage(event);
        }
      };

      for (const eventName of CHECK_EVENT_NAMES) {
        source.addEventListener(eventName, handleNamedCheckEvent);
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
      closeCurrentSource();
    };
  }, [checkId, detail, refreshDetail]);

  const visibleDetail = detail?.check_id === checkId ? detail : null;
  const visibleError = detailError?.checkId === checkId ? detailError.error : null;

  return {
    detail: visibleDetail,
    error: visibleError,
    loading: loading || (visibleDetail === null && visibleError === null),
    refreshDetail,
    state,
  };
}

function parseSopQualityCheckEvent(data: string): SopQualityCheckEvent | null {
  if (!data.trim()) {
    return null;
  }

  try {
    const event = JSON.parse(data) as Partial<SopQualityCheckEvent>;
    if (
      typeof event.check_id !== "string" ||
      typeof event.sequence !== "number" ||
      typeof event.type !== "string"
    ) {
      return null;
    }
    return event as SopQualityCheckEvent;
  } catch {
    return null;
  }
}

function nextCursor(
  currentCursor: number,
  message: MessageEvent<string>,
  event: SopQualityCheckEvent,
): number {
  const parsedId = Number.parseInt(message.lastEventId, 10);
  if (Number.isFinite(parsedId)) {
    return Math.max(currentCursor, parsedId);
  }
  return Math.max(currentCursor, event.sequence);
}

function isTerminalEvent(event: SopQualityCheckEvent): boolean {
  return (
    event.type === "completed" ||
    event.type === "failed" ||
    event.type === "interrupted"
  );
}

function isMessageEvent(event: Event): event is MessageEvent<string> {
  return (
    "data" in event &&
    typeof (event as MessageEvent<unknown>).data === "string"
  );
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

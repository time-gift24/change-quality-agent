import type { SessionMessage, SessionStreamEvent } from "./types";

export type SessionConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed";

export type SessionViewState = {
  latestSequence: number;
  messages: SessionMessage[];
  liveBuffers: Record<string, string>;
  connectionStatus: SessionConnectionStatus;
  thinking: Record<string, boolean>;
};

export function createInitialSessionViewState(): SessionViewState {
  return {
    latestSequence: 0,
    messages: [],
    liveBuffers: {},
    connectionStatus: "idle",
    thinking: {},
  };
}

export function hydrateSessionViewState(
  messages: SessionMessage[],
): SessionViewState {
  return {
    ...createInitialSessionViewState(),
    latestSequence: messages.reduce(
      (max, message) => Math.max(max, message.sequence),
      0,
    ),
    messages: [...messages],
  };
}

export function reduceSessionStreamEvent(
  state: SessionViewState,
  event: SessionStreamEvent,
): SessionViewState {
  if (event.type === "message") {
    const sequence = event.sequence;
    if (state.messages.some((existing) => existing.sequence === sequence)) {
      return state;
    }
    const stepKey = bufferKey(event.additional_kwargs);
    const { [stepKey]: _flushed, ...remainingBuffers } = state.liveBuffers;
    return {
      ...state,
      latestSequence: Math.max(state.latestSequence, sequence),
      messages: [
        ...state.messages,
        {
          id: `msg-${sequence}`,
          session_id: event.session_id,
          sequence,
          role: event.role,
          content: event.content,
          additional_kwargs: event.additional_kwargs,
          created_at: event.created_at ?? "",
        },
      ],
      liveBuffers: remainingBuffers,
    };
  }

  const stepKey = bufferKey(event.additional_kwargs);
  const channel = readString(event.additional_kwargs.channel);
  if (channel === "thinking") {
    return {
      ...state,
      thinking: { ...state.thinking, [stepKey]: true },
    };
  }
  if (!event.content) {
    return state;
  }
  return {
    ...state,
    liveBuffers: {
      ...state.liveBuffers,
      [stepKey]: `${state.liveBuffers[stepKey] ?? ""}${event.content}`,
    },
  };
}

export function projectSessionMessagesByStep(
  state: SessionViewState,
): Record<string, SessionMessage[]> {
  const grouped: Record<string, SessionMessage[]> = {};
  for (const message of state.messages) {
    const step = readString(message.additional_kwargs.step) ?? "unknown";
    grouped[step] = grouped[step] ?? [];
    grouped[step].push(message);
  }
  return grouped;
}

function bufferKey(additional: Record<string, unknown> | undefined): string {
  const step = readString(additional?.step);
  if (step) {
    return `step:${step}`;
  }
  const turnId = readString(additional?.turn_id);
  if (turnId) {
    return `turn:${turnId}`;
  }
  return "default";
}

function readString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

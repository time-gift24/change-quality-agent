import type { SessionViewState } from "../sessions/reducer";
import type {
  SopQualityCheckEvent,
  SopQualityDisplayState,
  SopQualityNodeState,
} from "./types";

export type SopQualityCheckViewState = {
  latestSequence: number;
  nodes: Record<string, SopQualityNodeState>;
  events: SopQualityCheckEvent[];
  needsRefresh: boolean;
  isRunning: boolean;
  connectionStatus: "idle" | "connecting" | "open" | "reconnecting" | "closed";
};

export function createInitialSopQualityCheckViewState(): SopQualityCheckViewState {
  return {
    latestSequence: 0,
    nodes: {},
    events: [],
    needsRefresh: false,
    isRunning: true,
    connectionStatus: "idle",
  };
}

export function hydrateFromDisplayState(
  displayState: SopQualityDisplayState,
): SopQualityCheckViewState {
  return {
    ...createInitialSopQualityCheckViewState(),
    latestSequence: displayState.latest_sequence,
    nodes: displayState.nodes,
    isRunning: displayState.is_running,
  };
}

export function reduceSopQualityCheckEvent(
  state: SopQualityCheckViewState,
  event: SopQualityCheckEvent,
): SopQualityCheckViewState {
  const nextState: SopQualityCheckViewState = {
    ...state,
    latestSequence: Math.max(state.latestSequence, event.sequence),
    events: [...state.events, event],
  };

  if (event.type === "checkpoint") {
    return {
      ...updateEventNode(nextState, event, "done"),
      needsRefresh: true,
    };
  }

  if (event.type === "started") {
    return {
      ...updateEventNode(nextState, event, "running"),
      isRunning: true,
    };
  }

  if (event.type === "messages") {
    return appendEventNodeMessage(nextState, event);
  }

  if (event.type === "updates") {
    return updateEventNode(nextState, event, "running");
  }

  if (event.type === "completed") {
    return {
      ...nextState,
      nodes: settleRunningNodes(nextState.nodes),
      needsRefresh: true,
      isRunning: false,
      connectionStatus: "closed",
    };
  }

  if (event.type === "failed" || event.type === "interrupted") {
    const status = event.type === "failed" ? "error" : "interrupted";
    return {
      ...updateEventNode(nextState, event, status),
      needsRefresh: true,
      isRunning: false,
      connectionStatus: "closed",
    };
  }

  return nextState;
}

export function getOrderedNodeIds(
  state: SopQualityCheckViewState,
  registeredNodeIds: string[],
): string[] {
  const registered = registeredNodeIds.filter((nodeId) => nodeId in state.nodes);
  const registeredSet = new Set(registeredNodeIds);
  const unknown = Object.entries(state.nodes)
    .filter(([nodeId]) => !registeredSet.has(nodeId))
    .sort(
      ([leftId, leftNode], [rightId, rightNode]) =>
        (leftNode.firstSequence ?? Number.MAX_SAFE_INTEGER) -
          (rightNode.firstSequence ?? Number.MAX_SAFE_INTEGER) ||
        leftId.localeCompare(rightId),
    )
    .map(([nodeId]) => nodeId);

  return [...registered, ...unknown];
}

function appendEventNodeMessage(
  state: SopQualityCheckViewState,
  event: SopQualityCheckEvent,
): SopQualityCheckViewState {
  if (!event.node) {
    return state;
  }

  const currentNode = state.nodes[event.node] ?? createNodeState();
  if (event.channel === "thinking") {
    return {
      ...state,
      nodes: {
        ...state.nodes,
        [event.node]: {
          ...currentNode,
          status: "running",
          thinkingText: event.message ?? currentNode.thinkingText,
          firstSequence: currentNode.firstSequence ?? event.sequence,
        },
      },
    };
  }

  if (event.channel === "summary") {
    return {
      ...state,
      nodes: {
        ...state.nodes,
        [event.node]: {
          ...currentNode,
          status: "running",
          streamText: event.message ?? currentNode.streamText,
          firstSequence: currentNode.firstSequence ?? event.sequence,
        },
      },
    };
  }

  if (event.channel === "result") {
    return state;
  }

  return {
    ...state,
    nodes: {
      ...state.nodes,
      [event.node]: {
        ...currentNode,
        status: "running",
        streamText: `${currentNode.streamText}${event.message ?? ""}`,
        firstSequence: currentNode.firstSequence ?? event.sequence,
      },
    },
  };
}

function updateEventNode(
  state: SopQualityCheckViewState,
  event: SopQualityCheckEvent,
  status: SopQualityNodeState["status"],
): SopQualityCheckViewState {
  if (!event.node) {
    return state;
  }

  const currentNode = state.nodes[event.node] ?? createNodeState();
  return {
    ...state,
    nodes: {
      ...state.nodes,
      [event.node]: {
        ...currentNode,
        status,
        streamText: event.message ?? currentNode.streamText,
        error: status === "error" ? event.message ?? currentNode.error : undefined,
        firstSequence: currentNode.firstSequence ?? event.sequence,
      },
    },
  };
}

function createNodeState(): SopQualityNodeState {
  return {
    status: "idle",
    streamText: "",
  };
}

function settleRunningNodes(
  nodes: Record<string, SopQualityNodeState>,
): Record<string, SopQualityNodeState> {
  return Object.fromEntries(
    Object.entries(nodes).map(([nodeId, node]) => [
      nodeId,
      node.status === "running" ? { ...node, status: "done" } : node,
    ]),
  );
}

const ORDERED_STEPS = [
  "load_sop",
  "review_sop",
  "summarize_result",
  "submit_result",
] as const;

export type SopProjection = {
  latestSequence: number;
  nodes: Record<string, SopQualityNodeState>;
};

export function projectSessionStateToSopView(
  sessionState: SessionViewState,
  isRunning = false,
): SopProjection {
  const seenSteps: string[] = [];
  const grouped: Record<string, string[]> = {};
  const firstSequence: Record<string, number> = {};

  for (const message of sessionState.messages) {
    const step = readString(message.additional_kwargs.step);
    if (!step) {
      continue;
    }
    if (!(step in grouped)) {
      grouped[step] = [];
      seenSteps.push(step);
      firstSequence[step] = message.sequence;
    }
    grouped[step].push(message.content ?? "");
  }

  let lastSeen = seenSteps[seenSteps.length - 1];

  if (isRunning) {
    for (const stepKey of Object.keys(sessionState.liveBuffers)) {
      if (stepKey.startsWith("step:")) {
        const step = stepKey.slice("step:".length);
        if (!(step in grouped)) {
          grouped[step] = [];
          seenSteps.push(step);
          firstSequence[step] = sessionState.latestSequence + 1;
        }
        lastSeen = step;
      }
    }
    for (const stepKey of Object.keys(sessionState.thinking)) {
      if (stepKey.startsWith("step:")) {
        const step = stepKey.slice("step:".length);
        if (!(step in grouped)) {
          grouped[step] = [];
          seenSteps.push(step);
          firstSequence[step] = sessionState.latestSequence + 1;
        }
        lastSeen = step;
      }
    }
  }

  const orderedSteps = sortSteps(seenSteps, firstSequence);
  const nodes: Record<string, SopQualityNodeState> = {};

  for (const step of orderedSteps) {
    const persistedChunks = grouped[step] ?? [];
    const isLast = isRunning && step === lastSeen;
    const liveText = sessionState.liveBuffers[`step:${step}`];
    const isThinking = sessionState.thinking[`step:${step}`] === true;

    const streamText =
      isLast && liveText !== undefined
        ? liveText
        : persistedChunks.join("\n");

    const node: SopQualityNodeState = {
      status: isLast ? "running" : "done",
      streamText,
      firstSequence: firstSequence[step],
    };

    if (isLast && isThinking) {
      node.thinkingText = "思考中";
    }

    nodes[step] = node;
  }

  return {
    latestSequence: sessionState.messages.reduce(
      (max, message) => Math.max(max, message.sequence),
      sessionState.latestSequence,
    ),
    nodes,
  };
}

function sortSteps(
  seen: string[],
  firstSequence: Record<string, number>,
): string[] {
  const orderedKnown = ORDERED_STEPS.filter((step) => seen.includes(step));
  const unknown = seen
    .filter((step) => !ORDERED_STEPS.includes(step as never))
    .sort(
      (left, right) =>
        (firstSequence[left] ?? Number.MAX_SAFE_INTEGER) -
        (firstSequence[right] ?? Number.MAX_SAFE_INTEGER),
    );
  return [...orderedKnown, ...unknown];
}

function readString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

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

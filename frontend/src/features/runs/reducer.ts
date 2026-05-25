import type { RunEvent } from "./types";

export type NodeRuntimeStatus =
  | "idle"
  | "running"
  | "done"
  | "error"
  | "interrupted";

export type NodeRuntime = {
  status: NodeRuntimeStatus;
  streamText: string;
  value?: unknown;
  progress?: unknown;
  error?: string;
  firstSequence?: number;
};

export type RunViewState = {
  latestSequence: number;
  nodes: Record<string, NodeRuntime>;
  events: RunEvent[];
  isRunning: boolean;
  connectionStatus: "idle" | "connecting" | "open" | "reconnecting" | "closed";
};

export function createInitialRunViewState(): RunViewState {
  return {
    latestSequence: 0,
    nodes: {},
    events: [],
    isRunning: true,
    connectionStatus: "idle",
  };
}

export function reduceRunEvent(
  state: RunViewState,
  event: RunEvent,
): RunViewState {
  const nextState: RunViewState = {
    ...state,
    latestSequence: Math.max(state.latestSequence, event.sequence),
    events: [...state.events, event],
  };

  if (event.type === "done") {
    return {
      ...nextState,
      isRunning: false,
      connectionStatus: "closed",
    };
  }

  if (event.type === "error") {
    const nextWithNode = event.node
      ? updateNode(
          nextState,
          event.node,
          (node) => ({
            ...node,
            status: "error",
            error: eventError(event),
          }),
          event.sequence,
        )
      : nextState;

    return {
      ...nextWithNode,
      isRunning: false,
      connectionStatus: "closed",
    };
  }

  if (!event.node) {
    return nextState;
  }

  if (event.type === "tasks") {
    return updateNode(
      nextState,
      event.node,
      (node) => ({
        ...node,
        status: taskStatus(event, node.status),
        error: taskError(event, node.error),
      }),
      event.sequence,
    );
  }

  if (event.type === "messages") {
    return updateNode(
      nextState,
      event.node,
      (node) => ({
        ...node,
        status: node.status === "idle" ? "running" : node.status,
        streamText: `${node.streamText}${messageDelta(event)}`,
      }),
      event.sequence,
    );
  }

  if (event.type === "updates") {
    return updateNode(
      nextState,
      event.node,
      (node) => ({
        ...node,
        status: "done",
        value: updateValue(event),
      }),
      event.sequence,
    );
  }

  if (event.type === "custom") {
    return updateNode(
      nextState,
      event.node,
      (node) => ({
        ...node,
        progress: event.payload.progress,
      }),
      event.sequence,
    );
  }

  return ensureNode(nextState, event.node, event.sequence);
}

export function getOrderedNodeIds(
  state: RunViewState,
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

function updateNode(
  state: RunViewState,
  nodeId: string,
  update: (node: NodeRuntime) => NodeRuntime,
  eventSequence: number,
): RunViewState {
  const currentNode = state.nodes[nodeId] ?? createNodeRuntime();
  const nextNode = update(currentNode);

  return {
    ...state,
    nodes: {
      ...state.nodes,
      [nodeId]: {
        ...nextNode,
        firstSequence: nextNode.firstSequence ?? eventSequence,
      },
    },
  };
}

function ensureNode(
  state: RunViewState,
  nodeId: string,
  eventSequence: number,
): RunViewState {
  return updateNode(state, nodeId, (node) => node, eventSequence);
}

function createNodeRuntime(): NodeRuntime {
  return {
    status: "idle",
    streamText: "",
  };
}

function taskStatus(
  event: RunEvent,
  fallback: NodeRuntimeStatus,
): NodeRuntimeStatus {
  const status = stringPayloadValue(event, "status");

  if (status === "started" || status === "running") {
    return "running";
  }

  if (
    status === "completed" ||
    status === "complete" ||
    status === "done" ||
    status === "success" ||
    status === "succeeded"
  ) {
    return "done";
  }

  if (status === "failed" || status === "error") {
    return "error";
  }

  if (status === "interrupted") {
    return "interrupted";
  }

  return fallback;
}

function taskError(event: RunEvent, fallback: string | undefined): string | undefined {
  return stringPayloadValue(event, "error") ?? fallback;
}

function eventError(event: RunEvent): string | undefined {
  return (
    stringPayloadValue(event, "error") ??
    stringPayloadValue(event, "message") ??
    "Run event failed"
  );
}

function messageDelta(event: RunEvent): string {
  return (
    stringPayloadValue(event, "delta") ??
    stringPayloadValue(event, "text") ??
    stringPayloadValue(event, "content") ??
    ""
  );
}

function updateValue(event: RunEvent): unknown {
  if ("value" in event.payload) {
    return event.payload.value;
  }

  return event.payload;
}

function stringPayloadValue(event: RunEvent, key: string): string | undefined {
  const value = event.payload[key];

  return typeof value === "string" ? value : undefined;
}

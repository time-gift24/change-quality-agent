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
      nodes: settleRunningNodes(nextState.nodes),
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
      (node) => {
        const nextStatus = taskStatus(event, node.status);

        return {
          ...node,
          status: nextStatus,
          error: taskError(event, nextStatus, node.error),
        };
      },
      event.sequence,
    );
  }

  if (event.type === "messages") {
    return updateNode(
      nextState,
      event.node,
      (node) => {
        const finalText = finalMessageText(event);

        return {
          ...node,
          status: node.status === "idle" ? "running" : node.status,
          streamText:
            finalText === undefined
              ? `${node.streamText}${messageDelta(event)}`
              : mergeFinalMessageText(node.streamText, finalText),
        };
      },
      event.sequence,
    );
  }

  if (event.type === "updates") {
    return updateNode(
      nextState,
      event.node,
      (node) => ({
        ...node,
        status: isFailureStatus(node.status) ? node.status : "done",
        value: updateValue(event),
      }),
      event.sequence,
    );
  }

  if (event.type === "custom") {
    if (event.node === "start" && event.payload.progress === undefined) {
      return nextState;
    }

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

function settleRunningNodes(
  nodes: Record<string, NodeRuntime>,
): Record<string, NodeRuntime> {
  return Object.fromEntries(
    Object.entries(nodes).map(([nodeId, node]) => [
      nodeId,
      node.status === "running" ? { ...node, status: "done" } : node,
    ]),
  );
}

function isFailureStatus(status: NodeRuntimeStatus): boolean {
  return status === "error" || status === "interrupted";
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

function taskError(
  event: RunEvent,
  status: NodeRuntimeStatus,
  fallback?: string,
): string | undefined {
  if (status !== "error" && status !== "interrupted") {
    return undefined;
  }

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

function finalMessageText(event: RunEvent): string | undefined {
  const messages = event.payload.messages;
  if (!Array.isArray(messages)) {
    return stringPayloadValue(event, "final_text");
  }

  return (
    findMessageText(messages, isAssistantMessage) ??
    findMessageText(messages, () => true)
  );
}

function findMessageText(
  messages: unknown[],
  predicate: (message: Record<string, unknown>) => boolean,
): string | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (!isRecord(message) || !predicate(message)) {
      continue;
    }

    const text = messageContentText(message.content);
    if (text !== undefined) {
      return text;
    }
  }

  return undefined;
}

function isAssistantMessage(message: Record<string, unknown>): boolean {
  return message.role === "assistant" || message.type === "ai";
}

function messageContentText(content: unknown): string | undefined {
  if (typeof content === "string") {
    return content;
  }

  if (!Array.isArray(content)) {
    return undefined;
  }

  const parts = content.flatMap((part) => {
    if (typeof part === "string") {
      return [part];
    }

    if (isRecord(part) && typeof part.text === "string") {
      return [part.text];
    }

    return [];
  });

  return parts.length > 0 ? parts.join("") : undefined;
}

function mergeFinalMessageText(currentText: string, finalText: string): string {
  if (currentText === finalText || finalText.startsWith(currentText)) {
    return finalText;
  }

  if (currentText.endsWith(finalText)) {
    return currentText;
  }

  return finalText;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

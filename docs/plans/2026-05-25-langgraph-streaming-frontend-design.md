# LangGraph Streaming Frontend Design

Date: 2026-05-25

## Context

This project currently has a minimal Python entry point and depends on
`langgraph>=1.2.1` and FastAPI. The approved direction is to support a
multi-node LangGraph workflow where the backend streams structured execution
events and the frontend renders node progress, node outputs, token streams,
history, and recoverable errors without flattening everything into one text
response.

Official references:

- https://docs.langchain.com/oss/python/langgraph/streaming
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/javascript/langgraph/frontend/overview
- https://docs.langchain.com/oss/javascript/langgraph/frontend/graph-execution
- https://docs.langchain.com/langgraph-platform/use-stream-react

## Goals

- Stream every run as structured events over a stable API.
- Preserve node identity for progress, partial LLM output, final node outputs,
  custom progress, checkpoints, and errors.
- Let the frontend render a deterministic pipeline view even when events arrive
  from parallel nodes.
- Keep final assistant messages separate from internal node output.
- Make the design compatible with persistent threads and future checkpoint
  replay.

## Non-goals

- Do not implement a custom checkpoint storage engine.
- Do not expose raw provider-specific token events directly to UI components.
- Do not require LangGraph Platform. A self-hosted FastAPI streaming endpoint is
  the baseline, while the frontend model should still map cleanly to the
  official `useStream` shape later.

## Backend Architecture

The backend exposes one streaming run endpoint:

```text
POST /threads/{thread_id}/runs/stream
```

The handler invokes the compiled graph with a config containing the thread ID:

```python
config = {"configurable": {"thread_id": thread_id}}
```

The graph is streamed with multiple modes:

```python
stream_mode = ["tasks", "messages", "updates", "custom", "checkpoints"]
```

Each raw LangGraph chunk is adapted into a normalized server-sent event. The
adapter is intentionally thin: it keeps the original payload available, but
adds stable top-level routing fields so frontend code does not need to know
LangGraph internals.

## Event Contract

Every event sent to the browser should use this envelope:

```json
{
  "type": "messages",
  "node": "generate_answer",
  "thread_id": "thread-123",
  "run_id": "run-456",
  "checkpoint_id": "checkpoint-789",
  "sequence": 12,
  "payload": {}
}
```

Required fields:

- `type`: one of `tasks`, `messages`, `updates`, `custom`, `checkpoints`,
  `error`, or `done`.
- `node`: LangGraph node name when known. For graph-level events this may be
  null.
- `thread_id`: caller-provided conversation or workflow thread ID.
- `run_id`: backend-generated run ID for this invocation.
- `sequence`: monotonically increasing event number for this run.
- `payload`: normalized event body plus the original LangGraph chunk when useful.

Optional fields:

- `checkpoint_id`: included when available.
- `task_id`: included for task lifecycle events.
- `parent_node`: included for subgraph events.

## Event Mapping

`messages` events represent token or message chunks produced inside a node.
The backend should derive `node` from `metadata.langgraph_node` when available.
The frontend appends message content to that node's streaming buffer.

`updates` events represent state writes after a node finishes a step. The node
name is usually the top-level key in the chunk. The frontend marks the node as
done and stores the update under that node and under the relevant state key.

`tasks` events represent node lifecycle, failure, retry, or interrupt status.
The frontend uses them for status indicators and error surfaces.

`custom` events are for domain progress emitted by node code, such as retrieval
progress or validation counts.

`checkpoints` events expose checkpoint IDs and state snapshots needed for
resume, replay, and future time-travel debugging.

`error` is emitted by the API adapter when streaming fails before LangGraph can
encode the failure as a task event.

`done` is emitted once the stream closes cleanly.

## Frontend State Model

The frontend owns a pipeline registry rather than deriving UI order from event
arrival order:

```ts
const PIPELINE_NODES = [
  { id: "classify", label: "Classify", stateKey: "classification" },
  { id: "retrieve", label: "Retrieve", stateKey: "documents" },
  { id: "analyze", label: "Analyze", stateKey: "analysis" },
  { id: "generate_answer", label: "Answer", stateKey: "messages" },
];
```

Runtime state is reduced from events:

```ts
type NodeRuntime = {
  status: "idle" | "running" | "done" | "error";
  streamText: string;
  value?: unknown;
  progress?: unknown;
  error?: string;
};
```

The reducer updates:

- `messages`: final user-visible conversation messages.
- `nodes`: per-node status, partial text, final value, and error state.
- `values`: latest graph state assembled from updates or values.
- `checkpoints`: ordered checkpoint metadata for restore and replay.
- `isRunning`: true until `done` or terminal `error`.

## Rendering Rules

- Show one stable card or row per pipeline node.
- Use `tasks` to show running, failed, interrupted, and retry states.
- Use `messages` to stream partial text into the producing node.
- Use `updates` to show completed node output.
- Render the final assistant response only from the designated answer node or
  the `messages` state key.
- Keep internal node reasoning, retrieval payloads, and validation output out of
  the final chat transcript unless the product explicitly promotes them.
- Keep pipeline display order fixed from `PIPELINE_NODES`, especially when nodes
  run in parallel.

## Persistence

The streaming design assumes a persistent checkpointer. For production, use a
database-backed LangGraph checkpointer, with Postgres as the default choice.
Every run must pass `thread_id` in graph config. Checkpoint IDs from stream
events should be retained by the frontend so later views can load history,
resume an interrupted run, or inspect prior states.

Short-term workflow history belongs in graph state and checkpoints. Long-term
cross-thread memory belongs in a store, not in an unbounded checkpoint state.

## Error Handling

- If a node fails, keep prior completed node outputs visible.
- Mark only the failed node as `error` when the node is known.
- Emit a graph-level `error` when the failure cannot be tied to a node.
- Close streams with a terminal `done` or `error`; do not leave clients waiting.
- Preserve `run_id`, `sequence`, and latest `checkpoint_id` in error payloads.

## Testing Strategy

Backend tests:

- Verify that raw LangGraph chunks are adapted into the event envelope.
- Verify node extraction from message metadata.
- Verify update extraction from node-keyed chunks.
- Verify sequence numbers are monotonic.
- Verify stream errors emit terminal `error` events.

Frontend tests:

- Feed sample event streams into the reducer and assert node status changes.
- Verify token chunks append to the correct node.
- Verify parallel node event arrival does not reorder the UI.
- Verify final answer rendering excludes internal node text.
- Verify failed nodes keep earlier node results visible.

Integration tests:

- Run a small graph with at least three nodes and one LLM-streaming node.
- Assert the client receives `tasks`, `messages`, `updates`, and `done`.
- Assert a repeated request with the same `thread_id` can load persisted state.

## Open Decisions

- Choose the frontend stack and whether to use the official React `useStream`
  hook directly or a local `useGraphRunStream` wrapper first.
- Choose the initial Postgres deployment path and migration ownership for
  checkpointer setup.
- Decide which graph nodes are product-visible and which remain internal.

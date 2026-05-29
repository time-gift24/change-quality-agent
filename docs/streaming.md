# Streaming Architecture

This document captures the durable streaming model used by SOP quality checks
and the shared agent session transcript system. Planning drafts previously kept
under `docs/plans/` have been removed; this file is the stable reference for the
implemented behavior.

## Scope

The streaming stack has two separate concerns:

- SOP quality lifecycle: lightweight business events for one quality check.
- Session transcript: durable assistant/tool messages plus live token deltas for
  any agent-style conversation.

These concerns intentionally use different endpoints and different cursors. A
client must not reuse a SOP event cursor as a session message cursor.

## Storage

`sop_quality_checks` stores the business check record:

- `sop_id` and `env_key` identify the subject being checked.
- `status` is `pending`, `running`, `succeeded`, `failed`, `cancelled`, or
  `interrupted`.
- `thread_id`, `checkpoint_ns`, and `current_checkpoint_id` identify the
  LangGraph checkpoint state.
- `session_id` links the check to the shared transcript when one exists.

`sop_quality_events` stores only lightweight lifecycle events:

- `sequence` is scoped to a single `check_id`.
- Events include `created`, `started`, `checkpoint`, `completed`, `failed`, and
  `interrupted`.
- Rows do not store token deltas or full transcript content.

`sessions` stores a reusable conversation identity:

- `id` is an internal autoincrement key.
- `thread_id` is the framework thread id and is also used as the SOP graph
  checkpoint `thread_id`.
- `status` is `active`, `completed`, `failed`, or `interrupted`.

`messages` stores durable transcript messages:

- `id` is a UUID.
- `sequence` is scoped to a single `session_id` and drives session replay.
- `role` is `user`, `assistant`, `tool`, or `system`.
- `content` is the durable message body.
- `additional_kwargs` stores rendering metadata such as `step`, `kind`, and
  tool-call details.

LangGraph Postgres checkpoints remain the source for graph state and resume
data. The application tables above provide business lookup, SSE cursors, and
plain transcript rendering.

## SOP Quality Flow

Starting a SOP quality check creates or joins the active check for the same
`sop_id` and `env_key`. New checks also create a session; the session
`thread_id` becomes the LangGraph checkpoint `thread_id`.

The graph currently has four steps:

1. `load_sop`: fetches SOP content through `SopClient`.
2. `review_sop`: runs a fresh DeepAgent instance through `AgentFactory`.
3. `summarize_result`: normalizes the review into the result shape.
4. `submit_result`: sends the final result to the external submit hook.

Graph execution uses a top-level LangGraph checkpoint namespace:

```python
{"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
```

Non-empty namespaces are reserved for LangGraph subgraph paths and should not be
used for the top-level SOP quality graph.

## SOP Stream

Endpoint:

```http
GET /api/sop-quality-checks/{check_id}/stream?after={event_sequence}
```

Contract:

- Replays persisted `sop_quality_events` where `sequence > after`.
- Uses `sop_quality_events.sequence` as the SSE `id`.
- Emits only check lifecycle events.
- Stops after terminal events: `completed`, `failed`, `cancelled`, or
  `interrupted`.
- Does not replay session messages and does not emit token deltas.

Use this stream for check status, checkpoint notifications, and lifecycle
completion. Use the session stream for transcript content.

## Session Stream

Endpoint:

```http
GET /api/sessions/{session_id}/stream?after={message_sequence}
```

Contract:

- Replays persisted `messages` where `sequence > after`.
- Emits persisted messages as `event: message` with SSE `id` equal to
  `messages.sequence`.
- Emits live token deltas as `event: message_delta` with `sequence: null`.
- Emits terminal events `completed`, `failed`, or `interrupted` with the
  `session_id`, then closes.
- Reconnects should use the latest persisted message sequence, not token delta
  count and not SOP event sequence.

Persisted `message` events advance the cursor. Live `message_delta` events are
display-only and are not durable transcript content.

## Message Writers And Live Deltas

Graph nodes write durable step output through `RepositorySessionMessageWriter`.
Each persisted step message includes `additional_kwargs.step`, allowing the UI to
group output by graph step.

`DeepAgentStreamRunner` owns DeepAgent token streaming:

- It publishes content deltas as live `message_delta` events.
- It publishes a thinking marker when reasoning content appears.
- It persists only the final assistant message for the step.

Reasoning text is not displayed. The UI only shows a generic thinking state.

## Frontend Projection

`frontend/src/features/sessions/` owns generic session streaming:

- `getSessionMessages(sessionId, after)` hydrates durable messages.
- `useSessionStream(sessionId)` opens the session SSE connection after
  hydration.
- `message` events update `messages` and `latestSequence`.
- `message_delta` events update live buffers but do not advance the durable
  cursor.
- Terminal events close the stream and suppress reconnect.

SOP quality UI combines two inputs while a check is active:

- SOP stream for lifecycle events and checkpoint refreshes.
- Session stream for transcript output when `session_id` is present.

For terminal checks, the frontend does not open SSE streams. It renders the
server-hydrated `display_state` from the detail endpoint.

`projectSessionStateToSopView` maps session messages into SOP node state by
`additional_kwargs.step`. The known step order is `load_sop`, `review_sop`,
`summarize_result`, and `submit_result`; unknown steps are ordered by their first
message sequence.

## Reconnect Rules

- SOP stream `after` is a SOP lifecycle event sequence.
- Session stream `after` is a session message sequence.
- Token deltas are live-only and must not be used as a replay cursor.
- Terminal session events close the EventSource and must not reconnect.
- If an active check is interrupted during process startup, it receives an
  `interrupted` lifecycle event so new checks for the same SOP/env can start.

## Active Check Safety

The database enforces at most one active SOP quality check per `sop_id` and
`env_key` with a partial unique index over statuses `pending` and `running`.

The runner only transitions `pending -> running`. If a delayed or duplicate
runner sees a check that is already terminal or interrupted, it skips execution
instead of reviving the check and blocking future work.

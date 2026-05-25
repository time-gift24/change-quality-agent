# SOP Runs API Design

Date: 2026-05-25

## Context

This project is a FastAPI + LangGraph service for change quality management.
SOP quality checking is the first product workflow, but the underlying run
model must support future checks for other change-management subjects.

The service will run LangGraph in-process for v1. Postgres 13.22 will store
business run history, event history, SOP snapshots, and final results. LangGraph
checkpoint storage remains separate and should use the official Postgres
checkpointer rather than the business `runs` table.

The existing LangGraph streaming design in
`docs/plans/2026-05-25-langgraph-streaming-frontend-design.md` is treated as a
general run-event substrate, not a frontend-only design.

## Goals

- Provide SOP-specific APIs to preview an SOP and start a quality run.
- Provide generic run APIs for progress, debug inspection, event replay, and
  streaming.
- Allow multiple users to query progress and subscribe to the same run events.
- Persist historical SOP snapshots, run events, and final results.
- Reject duplicate active runs for the same `(sop_id, env)` pair.
- Keep v1 compatible with future worker or LangGraph Server migration.

## Non-Goals

- Do not define the final structured quality report schema yet.
- Do not implement automatic resume after process restart in v1.
- Do not expose internal SOP client configuration through public APIs.
- Do not use LangGraph checkpoint tables as the business source of truth.

## Key Decisions

- Use a generic `runs` resource, not `quality_runs`.
- SOP is represented as `subject_type = "sop"` and `subject_id = sop_id`.
- The uniqueness boundary for active SOP runs is `(sop_id, env_key)`.
- Duplicate active scheduling returns `409 Conflict` with the existing run ID.
- Environment query values use stable English keys such as `dev` or `prod`.
- Environment Chinese and English display names come from configuration.
- SOP client integration is mocked in v1; the interface should be shaped for a
  future real client implementation.
- Streaming uses SSE with persisted event replay.

## Architecture

The v1 architecture has four layers:

1. `app/api/v1/sop.py` exposes SOP-specific APIs.
2. `app/api/v1/runs.py` exposes generic run observation APIs.
3. `app/core/config.py` reads environment definitions from configuration.
4. `app/services/sop_quality.py` coordinates scheduling, run persistence,
   LangGraph execution, and event persistence.

LangGraph code belongs under `agent/`. FastAPI routes should validate input,
call services, and shape HTTP responses. They should not contain graph business
logic.

The high-level flow is:

1. A caller requests `POST /api/sop/{sop_id}/runs?env={env_key}`.
2. The service validates the environment key.
3. The mocked SOP client fetches the current SOP information.
4. The service creates a `runs` row in a transaction.
5. A Postgres partial unique index rejects another active run for the same
   `active_conflict_key`.
6. After commit, an in-process background task invokes the LangGraph workflow.
7. The service adapts LangGraph chunks into normalized `run_events`.
8. Users observe the run through `GET /api/runs/{run_id}` and SSE.

## API Design

### SOP Entry APIs

`GET /api/sop/environments`

Returns configured environments:

```json
[
  {
    "key": "dev",
    "name_zh": "开发",
    "name_en": "Development"
  }
]
```

Internal client parameters are never returned.

`GET /api/sop/{sop_id}?env=dev`

Fetches the current SOP from the SOP client for preview. This endpoint does not
create a run and does not write history.

`POST /api/sop/{sop_id}/runs?env=dev`

Starts a quality run for the SOP in the requested environment.

Successful response:

```http
202 Accepted
```

```json
{
  "run_id": "uuid",
  "status": "pending",
  "status_url": "/api/runs/uuid",
  "events_url": "/api/runs/uuid/events"
}
```

Duplicate active run response:

```http
409 Conflict
```

```json
{
  "message": "An active run already exists for this SOP and environment.",
  "active_run_id": "uuid",
  "status_url": "/api/runs/uuid",
  "events_url": "/api/runs/uuid/events"
}
```

`GET /api/sop/{sop_id}/runs?env=dev&limit=20`

Returns historical runs for one SOP and environment, ordered newest first.

### Generic Run APIs

`GET /api/runs/{run_id}`

Returns the stable business projection:

```json
{
  "run_id": "uuid",
  "subject_type": "sop",
  "subject_id": "payment-release",
  "env_key": "dev",
  "status": "running",
  "current_node": "check_steps",
  "completed_nodes": ["load_sop"],
  "latest_sequence": 12,
  "started_at": "2026-05-25T10:00:00Z",
  "finished_at": null,
  "result_status": null,
  "error_summary": null
}
```

`GET /api/runs/{run_id}?debug=true`

Adds implementation details for internal/debug use:

```json
{
  "thread_id": "quality-run:uuid",
  "current_checkpoint_id": "checkpoint-id",
  "langgraph_state_snapshot": {},
  "raw_graph_output": {},
  "raw_last_event": {}
}
```

`GET /api/runs/{run_id}/events?after=12`

Streams Server-Sent Events. The server first replays persisted events after the
requested sequence, then follows new events until terminal `done` or `error`.
Multiple users may subscribe to the same run.

## Environment Configuration

Environments are read from configuration, not from the database. Each
environment has:

- `key`: stable English API and database value.
- `name_zh`: Chinese display name.
- `name_en`: English display name.
- Internal SOP client settings, which are never returned by API responses.

Each run stores an `env_snapshot` in metadata so historical records keep the
display names used at execution time.

## SOP Client Boundary

The SOP client is an internal dependency with an interface shaped like:

```python
class SopClient:
    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        ...
```

v1 should provide a mock implementation. The mock returns deterministic SOP
data for tests and local development. The real implementation will be added
later by the project owner.

The run scheduler should depend on the interface, not on the mock directly.
This keeps the future client replacement local to dependency wiring.

## Database Design

### `runs`

`runs` is the business source of truth and the historical run table.

Suggested fields:

- `id UUID PRIMARY KEY`
- `thread_id TEXT NOT NULL`
- `assistant_id TEXT NOT NULL`
- `status TEXT NOT NULL`
- `active_conflict_key TEXT`
- `metadata JSONB NOT NULL`
- `kwargs JSONB NOT NULL`
- `current_checkpoint_id TEXT`
- `current_node TEXT`
- `completed_nodes JSONB NOT NULL DEFAULT '[]'`
- `subject_snapshot JSONB NOT NULL`
- `result_status TEXT`
- `structured_result JSONB`
- `raw_graph_output JSONB`
- `error JSONB`
- `created_by TEXT`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`
- `started_at TIMESTAMPTZ`
- `finished_at TIMESTAMPTZ`

`metadata` should include:

```json
{
  "subject_type": "sop",
  "subject_id": "payment-release",
  "env_key": "dev",
  "env_snapshot": {
    "key": "dev",
    "name_zh": "开发",
    "name_en": "Development"
  },
  "active_conflict_key": "sop:payment-release:env:dev"
}
```

`structured_result` is intentionally a TODO-shaped JSONB container until the
quality report schema is finalized.

### `run_events`

`run_events` stores the durable event stream for replay and SSE.

Suggested fields:

- `id BIGSERIAL PRIMARY KEY`
- `run_id UUID NOT NULL REFERENCES runs(id)`
- `sequence BIGINT NOT NULL`
- `type TEXT NOT NULL`
- `node TEXT`
- `thread_id TEXT NOT NULL`
- `checkpoint_id TEXT`
- `task_id TEXT`
- `payload JSONB NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`

Indexes:

```sql
CREATE UNIQUE INDEX uq_run_events_run_sequence
ON run_events (run_id, sequence);
```

### Active Run Constraint

SOP scheduling uses:

```text
active_conflict_key = "sop:{sop_id}:env:{env_key}"
```

Postgres enforces the active uniqueness boundary:

```sql
CREATE UNIQUE INDEX uq_runs_active_conflict_key
ON runs (active_conflict_key)
WHERE status IN ('pending', 'running');
```

Historical terminal runs remain queryable and do not block new scheduling.

### LangGraph Checkpoint Storage

The official LangGraph Postgres checkpointer should manage checkpoint tables.
`runs.thread_id` is passed into graph config:

```python
config = {"configurable": {"thread_id": run.thread_id}}
```

`runs.current_checkpoint_id` stores only the latest checkpoint pointer. Full
checkpoint state should be read from LangGraph when debug information is
requested.

## Status Model

Use the official run-style status values:

- `pending`
- `running`
- `success`
- `error`
- `timeout`
- `interrupted`

v1 has no queue. `pending` is brief and only exists after the row is created and
before the in-process task starts.

On service startup, any leftover `pending` or `running` run is marked
`interrupted`, and a system event is written. v1 does not attempt automatic
resume from checkpoint.

## Event Contract

Every stored and streamed event uses this envelope:

```json
{
  "type": "updates",
  "node": "check_sop_steps",
  "thread_id": "quality-run:uuid",
  "run_id": "uuid",
  "checkpoint_id": "checkpoint-id",
  "sequence": 12,
  "payload": {}
}
```

Supported event types:

- `tasks`: node lifecycle, retry, failure, and interrupt events.
- `messages`: LLM or message chunks attributed to a node.
- `updates`: graph state writes after a node step.
- `custom`: domain progress emitted by node code.
- `checkpoints`: checkpoint pointers and state snapshot summaries.
- `error`: graph or adapter failures.
- `done`: clean stream termination.

The database replay is the source of truth. An in-process broadcast channel may
be used for lower latency, but missed notifications must be recoverable by
polling persisted events.

## Error Handling

- `400 Bad Request`: missing or invalid request parameters.
- `404 Not Found`: unknown environment key or SOP not found.
- `409 Conflict`: active run already exists for `(sop_id, env_key)`.
- `502 Bad Gateway`: SOP client fails before a run is created.
- `500 Internal Server Error`: unexpected service or persistence error.

The scheduler should fetch the SOP before creating the run. If the SOP client
fails, no empty run history is created.

After a run is created, all execution failures must be persisted in `runs` and
`run_events`.

## Testing Strategy

API tests:

- Environment listing returns only public environment fields.
- SOP preview uses the mock client and does not create a run.
- Starting a run returns `202 Accepted`.
- Duplicate active `(sop_id, env_key)` scheduling returns `409 Conflict`.
- Different SOPs or environments can run concurrently.
- Historical run listing returns terminal runs newest first.

Persistence and concurrency tests:

- The partial unique index blocks only `pending` and `running` runs.
- Terminal runs do not block future scheduling.
- Startup cleanup marks leftover active runs as `interrupted`.
- SOP snapshots and environment snapshots are saved with each run.

Event tests:

- LangGraph chunks adapt into the stable event envelope.
- Per-run event sequences are monotonic.
- `after` replays missed events.
- Multiple subscribers can observe the same run.
- Streams terminate with `done` or `error`.

Result tests:

- `structured_result` remains shape-agnostic in v1.
- `raw_graph_output` is persisted.
- `debug=true` includes LangGraph public fields.
- Default run responses do not expose raw debug payloads.

## Open Decisions

- Final structured SOP quality report schema.
- Authentication and authorization rules for `debug=true`.
- Whether `created_by` comes from auth middleware, headers, or a future user
  table.
- Migration tool ownership for Postgres schema changes.
- Exact graph node list and which nodes are product-visible.

# SOP Quality Checkpoint Design

Date: 2026-05-28

## Goal

SOP quality checks should execute a fixed code-defined LangGraph graph, reuse
LangGraph checkpointing as the source of truth for graph state and messages, and
guarantee that the same SOP in the same environment has at most one active
quality check globally.

All users who open the same active SOP/environment check should see the same
business state, recover existing progress, and continue receiving live output.

## Non-Goals

- Do not introduce `graphs` or `graph_versions` tables in the first phase.
- Do not model SOP quality checks as ReAct agent test runs.
- Do not keep the generic `runs` and `run_events` model as the primary storage
  for SOP quality checks.
- Do not duplicate full LangGraph state, message history, findings, or report
  payloads into an event log.

## Core Principles

- LangGraph checkpoint tables store graph state, messages, tool state, and
  resume state.
- `sop_quality_checks` stores SOP quality check business history, lifecycle
  status, result summary, and the latest checkpoint pointer.
- `sop_quality_events` stores only lightweight lifecycle notifications for SSE
  reconnection. It is not a state store.
- The first implementation executes one code-defined graph:
  `graph_name = "sop_quality"`.
- The graph version is a code constant, for example
  `SOP_QUALITY_GRAPH_VERSION = "sop-quality@1"`.

## Data Model

### `sop_quality_checks`

This is the SOP quality check business table and history table.

```text
id UUID primary key

sop_id text not null
env_key text not null

graph_name text not null
graph_version text not null

thread_id text not null
checkpoint_ns text not null
current_checkpoint_id text null

status text not null
quality_result text null

sop_snapshot jsonb not null
result jsonb null
error jsonb null

created_by text null
created_at timestamptz not null
updated_at timestamptz not null
started_at timestamptz null
finished_at timestamptz null
```

Status values:

```text
pending
running
succeeded
failed
cancelled
interrupted
```

`quality_result` is a denormalized field for filtering and list views. The full
business result is stored in `result`.

Example `result`:

```json
{
  "quality_result": "warn",
  "summary": "发现 2 个中风险问题",
  "findings": [
    {
      "severity": "medium",
      "title": "缺少回滚条件",
      "step_id": "deploy",
      "recommendation": "补充失败回滚触发条件"
    }
  ],
  "report_markdown": "..."
}
```

The table keeps historical rows. The active uniqueness rule is enforced with a
Postgres partial unique index:

```sql
create unique index uq_sop_quality_checks_active_subject_env
on sop_quality_checks (sop_id, env_key)
where status in ('pending', 'running');
```

Postgres 13 supports this partial unique index. It means: at the same time, a
given `(sop_id, env_key)` can have only one active quality check. Terminal rows
such as `succeeded`, `failed`, `cancelled`, and `interrupted` are outside the
partial index, so history is preserved.

Recommended indexes:

```sql
create index ix_sop_quality_checks_subject_history
on sop_quality_checks (sop_id, env_key, created_at desc);

create index ix_sop_quality_checks_env_history
on sop_quality_checks (env_key, created_at desc);

create index ix_sop_quality_checks_status_updated
on sop_quality_checks (status, updated_at desc);
```

### `sop_quality_events`

This table is a lightweight notification log for reconnection and lifecycle
observation. It deliberately does not store full payloads.

```text
id bigserial primary key
check_id UUID not null references sop_quality_checks(id)

sequence bigint not null
type text not null
node text null
checkpoint_id text null
task_id text null
message text null
created_at timestamptz not null
```

Event types for the first phase:

```text
created
started
checkpoint
completed
failed
interrupted
```

Constraint:

```sql
create unique index uq_sop_quality_events_check_sequence
on sop_quality_events (check_id, sequence);
```

Field roles:

- `sequence`: per-check monotonic cursor for SSE reconnection.
- `type`: lifecycle boundary or checkpoint notification.
- `node`: graph node name when known.
- `checkpoint_id`: latest checkpoint associated with the event.
- `task_id`: LangGraph task id for diagnostics when available.
- `message`: short status text or error summary only.

No `payload` column is included. Model output, findings, report content, and
complete graph state are not duplicated into this table.

## LangGraph Checkpointing

Each SOP quality check gets a `thread_id` and `checkpoint_ns`.

Runtime config:

```python
config = {
    "configurable": {
        "thread_id": check.thread_id,
        "checkpoint_ns": check.checkpoint_ns,
    }
}
```

LangGraph checkpoint storage is responsible for:

- graph state
- message history
- tool state
- resume state
- checkpoint history

`sop_quality_checks.current_checkpoint_id` points at the latest checkpoint the
application has observed.

## Creation And Concurrency

Request:

```text
POST /api/sop-quality-checks?sop_id=<id>&env=<env_key>
```

Service behavior:

1. Fetch the current SOP snapshot.
2. Try to create a `sop_quality_checks` row with `status = pending`.
3. If an active row already exists for `(sop_id, env_key)`, return that existing
   check instead of creating a new one.
4. If two requests race, the partial unique index is the final guard. The loser
   catches `IntegrityError`, queries the active check, and returns it.
5. Write a `created` event for newly created checks.
6. Schedule the background runner.

This gives global sharing: every user who triggers the same active SOP/env
quality check receives the same `check_id`.

## Execution Flow

1. The background runner loads `sop_quality_checks`.
2. It marks the check `running`, sets `started_at`, and writes a `started` event.
3. It executes the fixed code-defined SOP quality LangGraph graph with the
   check's `thread_id` and `checkpoint_ns`.
4. When a checkpoint is produced:
   - update `sop_quality_checks.current_checkpoint_id`
   - write a `checkpoint` event
   - notify connected stream subscribers
5. On success:
   - write `status = succeeded`
   - write `quality_result`
   - write `result`
   - set `finished_at`
   - write a `completed` event
6. On failure:
   - write `status = failed`
   - write `error`
   - set `finished_at`
   - write a `failed` event
7. On service startup, leftover `pending` or `running` checks are marked
   `interrupted` and receive an `interrupted` event.

## Streaming And Recovery

The system has two different data paths:

- Live streaming: current in-process LangGraph output is broadcast to connected
  clients.
- Recovery: page refresh or late join reads checkpoint-derived state from
  LangGraph checkpoint storage.

The event table supports reconnection. It does not replay token deltas.

SSE reconnection flow:

```text
GET /api/sop-quality-checks/{check_id}/stream?after=0
```

Each stored event is emitted with `id = sequence`.

If the client disconnects after event `12`, it reconnects with:

```text
GET /api/sop-quality-checks/{check_id}/stream?after=12
```

The server sends events with `sequence > 12`, then continues waiting for new
events while the check is active.

If missed events include a newer checkpoint, the client refreshes check state
from the checkpoint-derived state endpoint or check detail endpoint.

## Multi-User Behavior

### User A starts a check

1. User A creates a check.
2. A new `sop_quality_checks` row is inserted.
3. A opens the stream endpoint.
4. The single background runner broadcasts live output to A.

### User B opens the same SOP/env

1. User B calls the same create endpoint.
2. The service returns the existing active `check_id`.
3. B navigates to the check page.
4. The page loads check detail and checkpoint-derived state, recovering prior
   progress.
5. B opens the same stream endpoint and receives subsequent live output.

## Broadcast Layer

First phase can use an in-process broadcast registry:

```text
check_id -> subscriber queues
```

The background runner is the only producer for a check. Each SSE connection gets
its own queue. The runner publishes live stream deltas and checkpoint
notifications to all subscribers.

Future multi-process deployment can replace the in-process registry with Redis
pub/sub without changing the storage model.

## API Surface

Suggested endpoints:

```text
POST /api/sop-quality-checks?sop_id=&env=
GET  /api/sop-quality-checks/{check_id}
GET  /api/sop-quality-checks/{check_id}/events?after=
GET  /api/sop-quality-checks/{check_id}/stream?after=
GET  /api/sop-quality-checks?sop_id=&env=&limit=
```

Endpoint roles:

- `POST`: create a new active check or return the existing active check.
- `GET detail`: return business metadata, terminal result/error, latest
  checkpoint pointer, and checkpoint-derived display state.
- `GET events`: replay lightweight event notifications only.
- `GET stream`: replay lightweight events, then subscribe to live broadcast.
- `GET list`: show SOP quality check history.

## Code Deletion And Replacement

Because the current code has not shipped, the first implementation should remove
the old generic run storage from the SOP quality path instead of keeping
compatibility shims.

Backend deletion/replacement target:

- Delete `runs` and `run_events` as SOP quality storage.
- Remove `app/models/runs.py`, `app/repositories/runs.py`,
  `app/schemas/runs.py`, `app/api/v1/runs.py`, and
  `app/api/v1/run_views.py` if no other product surface still needs them.
- Remove `/api/runs/{run_id}` and `/api/runs/{run_id}/events` from the SOP
  quality flow.
- Remove `RunRepositoryDep` and `RunRepository` startup cleanup from SOP quality
  execution. Startup cleanup should target active `sop_quality_checks` instead.
- Replace `app/services/sop_quality.py` with a service centered on
  `sop_quality_checks`: create-or-return-active, load detail, list history, and
  drive the background runner.
- Replace SOP endpoints in `app/api/v1/sop.py` or move them into a dedicated
  `app/api/v1/sop_quality_checks.py` router using the new API surface.
- Rewrite `app/agent/sop_quality/graph.py` as the fixed code-defined LangGraph
  graph. It should not load `AgentRepository`, `AgentVersion`, `RunRepository`,
  or the current ReAct-oriented `AgentRuntime`.
- Add `app/models/sop_quality_checks.py`,
  `app/repositories/sop_quality_checks.py`,
  `app/schemas/sop_quality_checks.py`, and a focused stream/broadcast module for
  check subscribers.
- Add a database migration that creates `sop_quality_checks`,
  `sop_quality_events`, the partial unique active index, and the supporting
  history indexes.

The current `/api/agents/{agent_key}/test-runs` path is also coupled to
`runs/run_events` and the ReAct-oriented runtime. If it has no immediate product
use, delete that test-run path and its tests in this phase. If it must remain as
an internal experiment, it should be redesigned separately and must not keep SOP
quality dependent on the old run storage.

Tests and contracts should move with the product surface:

- Replace run repository/model/API tests with `sop_quality_checks` model,
  repository, API, stream, and concurrency tests.
- Update `api/` contracts from `/api/runs/*` and `/api/sop/*/runs` to
  `/api/sop-quality-checks/*`.
- Keep race-condition coverage for the partial unique index and
  `IntegrityError -> return active check` behavior.
- Keep reconnect coverage for `after=<sequence>` and checkpoint-refresh events.

## Frontend Adaptation

The frontend should stop treating SOP quality as a generic run observer.

Current SOP flow:

```text
ChatPage
-> startSopQualityRun()
-> runId
-> RunObserver(runId)
-> /api/runs/{run_id}
-> /api/runs/{run_id}/events
```

Target SOP flow:

```text
ChatPage
-> startSopQualityCheck()
-> checkId, kind = created | active
-> SopQualityCheckObserver(checkId)
-> /api/sop-quality-checks/{check_id}
-> /api/sop-quality-checks/{check_id}/stream?after=
```

Frontend replacement target:

- Add `frontend/src/features/sop-quality-checks/` with `api.ts`, `types.ts`,
  `hooks.ts`, `reducer.ts`, and
  `components/SopQualityCheckObserver.tsx`.
- Stop using `frontend/src/features/runs/*` from SOP pages.
- Change SOP URLs from `?runId=` to `?checkId=`.
- Update `frontend/src/features/sop/pages/ChatPage.tsx` to create or join a
  quality check, navigate to the shared `checkId`, and render
  `SopQualityCheckObserver`.
- Update recent/history sidebar code to list `sop_quality_checks` history and
  navigate by `checkId`.
- Delete `frontend/src/features/runs/*` if no non-SOP product surface remains
  after backend cleanup.

Frontend recovery behavior:

1. Load `GET /api/sop-quality-checks/{check_id}` first. This returns business
   metadata, terminal result/error, latest checkpoint pointer, and
   checkpoint-derived display state.
2. Open `GET /api/sop-quality-checks/{check_id}/stream?after=<last_sequence>`.
3. Apply lightweight lifecycle events to local UI state.
4. When a `checkpoint` event arrives, refresh check detail or the
   checkpoint-derived display state.
5. Append live deltas from the in-process broadcast only for the current
   connection. Do not rely on event replay to reconstruct token-level output.

This satisfies both product cases: the original user sees normal live output,
and a second user who joins the same active SOP/env lands on the same check page,
recovers prior state from checkpoints, and receives subsequent live output.

## Why Not Keep `runs` And `run_events`

The current `runs` table mixes execution, business history, concurrency control,
and LangGraph checkpoint metadata. The current `run_events` table stores generic
event payloads and can drift into a second state store.

Because this code has not shipped, the first implementation should replace them
for SOP quality checks with domain-specific storage:

- `sop_quality_checks` for business history and state pointers.
- `sop_quality_events` for lightweight lifecycle notifications.
- LangGraph checkpoints for real graph state.

This is simpler, clearer, and closer to the product's first requirement.

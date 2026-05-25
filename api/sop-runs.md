# SOP Runs API Contract

This document is the shared v1 contract for SOP run creation and run observation.
SOP fetching is mocked in v1; the real SOP client will plug into the existing
`SopClient` interface later.

## Endpoints

```text
GET  /api/sop/environments
GET  /api/sop/{sop_id}?env=dev
POST /api/sop/{sop_id}/runs?env=dev
GET  /api/sop/{sop_id}/runs?env=dev&limit=20
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}?debug=true
GET  /api/runs/{run_id}/events?after=0
```

`/api/runs/{run_id}` is generic. It does not expose SOP-only fields such as
`env_key` at the top level. SOP environment details are available through SOP
entry/history APIs and persisted run metadata.

Runs persist `subject_type`, `subject_id`, and `env_key` as first-class columns
for uniqueness and history queries. The metadata JSON keeps the same values for
debugging and future generic run types.

## Run Events

`GET /api/runs/{run_id}/events` streams Server-Sent Events. The server first
replays persisted events with `sequence > after`, then polls persisted events
until it sends terminal `done` or `error`.

Each SSE frame uses:

```text
id: <sequence>
event: <type>
data: <json envelope>
```

The JSON envelope includes:

```json
{
  "run_id": "uuid",
  "sequence": 1,
  "type": "updates",
  "node": "validate_sop",
  "thread_id": "thread-id",
  "checkpoint_id": null,
  "task_id": null,
  "payload": {},
  "created_at": "2026-05-25T00:00:00Z"
}
```

Supported event types are `tasks`, `messages`, `updates`, `custom`,
`checkpoints`, `error`, and `done`.

## Error Responses

- `404 Not Found`: unknown environment key or SOP not found.
- `409 Conflict`: an active run already exists for the SOP/environment pair.
- `502 Bad Gateway`: SOP client failure before a run is created.
- `500 Internal Server Error`: unexpected service or persistence failure.

After a run is created, execution failures are persisted as an `error` event and
the run transitions to `error`.

## V1 Runtime Constraints

The in-process runner is a v1 substrate for local development and early backend
integration. It assumes a single active API worker for run execution. On service
startup, leftover `pending` and `running` runs are marked `interrupted`; automatic
checkpoint resume, official LangGraph Postgres checkpoint wiring, worker leases,
and heartbeat ownership are deferred to the real worker/checkpoint integration.
Checkpoint fields may be `null` in v1.

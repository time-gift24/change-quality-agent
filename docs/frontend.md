# Frontend Architecture

This document consolidates the former planning notes into the long-lived
reference for the browser app and its run-observation contract.

## Scope

The frontend is the first UI layer for Change Quality Agent. SOP quality checks
are the first workflow, and MCP server management is the first operational admin
workflow. The run UI is built on a generic substrate so future change quality
workflows can reuse the same observer, event reducer, and stream renderer.

The v1 backend runs LangGraph in the service process. Postgres stores business
run history and durable run events. LangGraph checkpoint storage stays separate
from the business `runs` table.

## Stack

- Vite
- React 19
- TypeScript
- Tailwind CSS v4 through `@tailwindcss/vite`
- React Router for page routing
- Streamdown for streamed markdown
- Vitest and React Testing Library for frontend tests
- Playwright smoke scripts for browser-level verification

Before implementing UI, read root `DESIGN.md`. It is the mandatory visual
contract for the frontend.

## Architecture

The frontend mirrors the backend split:

- `src/app` owns routing, shell layout, and route guards.
- `features/runs` is the reusable run observation substrate.
- `features/sop` is the SOP-specific wrapper.
- `features/mcp` is the MCP server management workspace.
- `src/app/App.tsx` mounts `/sop` and protected `/mcp` routes.
- `src/styles/globals.css` owns Tailwind, Streamdown, and design-token CSS.

Current structure:

```text
frontend/src/
  app/
    App.tsx
    AppShell.tsx
    routing/
      ProtectedRoute.tsx
      useAuthz.ts
  styles/
    globals.css
  lib/
    apiClient.ts
    sse.ts
  features/
    runs/
      api.ts
      types.ts
      reducer.ts
      hooks.ts
      components/
        RunObserver.tsx
        StreamMarkdown.tsx
    sop/
      api.ts
      types.ts
      hooks.ts
      pages/
        ChatPage.tsx
    mcp/
      api.ts
      types.ts
      hooks.ts
      components/
        McpServerList.tsx
        McpServerDetail.tsx
        McpServerFormDrawer.tsx
        errorMessages.ts
      pages/
        McpPage.tsx
```

Routes:

- `/` redirects to `/sop`.
- `/sop` renders the SOP quality workflow.
- `/mcp` renders the MCP management workspace behind `ProtectedRoute`.
- Unknown routes redirect to `/sop`.

`features/runs` only knows generic run concepts:

- `run_id`
- `subject_type`
- `subject_id`
- `status`
- `current_node`
- `completed_nodes`
- `latest_sequence`
- normalized run events

It must not read or display SOP `env_key` as a top-level generic run field.
SOP environment context stays in `features/sop` and SOP entry APIs.

`features/sop` owns:

- environment selection
- SOP ID input
- run creation
- `409 Conflict` join-existing-run behavior
- recent SOP run history
- handoff to the generic `RunObserver`

`features/mcp` owns:

- MCP server list and selected server state
- create, update, delete, start, stop, restart, and check actions
- detail refresh and tools snapshot display
- transport-specific form validation
- MCP-specific error message mapping and destructive-action confirmation

MCP route authorization is intentionally abstracted behind `useAuthz()`. The
current placeholder returns admin access so the page can be developed and
tested; the real administrator policy should replace that hook without changing
MCP page code.

## API Contract

The shared API contract lives in `api/openapi.yml`. Backend and frontend should
keep that file current when endpoints change.

### SOP Entry APIs

`GET /api/sop/environments`

Returns public configured environments. Internal SOP client settings are never
returned.

```json
[
  {
    "key": "dev",
    "name_zh": "开发",
    "name_en": "Development"
  }
]
```

`GET /api/sop/{sop_id}?env=dev`

Fetches the current SOP from the SOP client for preview. This does not create a
run and does not write run history.

`POST /api/sop/{sop_id}/runs?env=dev`

Starts a quality run for the requested SOP and environment.

Accepted:

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

Duplicate active run:

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

The frontend treats `409` as a join path, not a hard page error.

`GET /api/sop/{sop_id}/runs?env=dev&limit=20`

Returns historical runs for one SOP and environment, newest first.

`GET /api/sop/recent/runs?env=dev&limit=20`

Returns recent SOP runs for one environment, newest first. The current sidebar
uses this endpoint so recent history is environment-scoped, not tied to the
currently typed SOP ID.

### Generic Run APIs

`GET /api/runs/{run_id}`

Returns the stable business projection:

```json
{
  "run_id": "uuid",
  "subject_type": "sop",
  "subject_id": "payment-release",
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

Generic run responses intentionally do not expose SOP-specific fields such as
top-level `env_key`.

`GET /api/runs/{run_id}?debug=true`

Adds internal/debug details such as thread ID, checkpoint pointer, raw graph
output, and the latest raw event. Default UI should not expose raw debug
payloads.

`GET /api/runs/{run_id}/events?after=12`

Streams Server-Sent Events. The server first replays persisted events with
sequence greater than `after`, then follows new events until terminal `done` or
`error`. Multiple users can subscribe to the same run.

### MCP Management APIs

The MCP page uses the `/api/mcp/servers` API family from `api/openapi.yml`.
These endpoints require the backend MCP admin token contract. The current
frontend route guard only controls page access; it does not replace the backend
`X-MCP-Admin-Token` requirement.

Used endpoints:

- `GET /api/mcp/servers`: list redacted server configurations and runtime
  summaries.
- `POST /api/mcp/servers`: create a server configuration.
- `GET /api/mcp/servers/{server_id}`: load detail plus latest tool snapshot.
- `PATCH /api/mcp/servers/{server_id}`: update stopped server configuration.
- `DELETE /api/mcp/servers/{server_id}`: delete a server configuration.
- `POST /api/mcp/servers/{server_id}/start`: start the server.
- `POST /api/mcp/servers/{server_id}/stop`: stop the server.
- `POST /api/mcp/servers/{server_id}/restart`: restart the server.
- `POST /api/mcp/servers/{server_id}/check`: refresh runtime status and tools.

API contract note: MCP server responses return `env` and `headers` as redacted
values. The current UI does not display or edit those fields. If a future UI
adds them, editing must be treated as value replacement and must not imply that
the frontend can recover secret plaintext from the backend.

## Event Model

Every stored and streamed event uses the same envelope:

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
- `error`: terminal graph or adapter failure.
- `done`: clean stream termination.

Frontend reducer behavior:

- `tasks` starts, completes, fails, or interrupts nodes.
- `messages` appends markdown text to the producing node.
- `updates` stores node output and usually marks the node done.
- `custom` stores node progress.
- `checkpoints` stays collapsed by default.
- `error` marks the run terminal and visible failure.
- `done` marks the run terminal and triggers summary refresh.

The browser keeps its reconnect cursor local. On reconnect, it uses the last
received SSE `id` or event `sequence`, keeps prior events visible, and requests:

```text
GET /api/runs/{run_id}/events?after={latestSequence}
```

## Data And Scheduling

Postgres 13.22 stores business run state in `runs` and replayable stream data in
`run_events`.

`runs` is the historical source of truth. Important fields include:

- `id`
- `thread_id`
- `assistant_id`
- `subject_type`
- `subject_id`
- `env_key`
- `status`
- `active_conflict_key`
- `metadata`
- `kwargs`
- `current_checkpoint_id`
- `current_node`
- `completed_nodes`
- `subject_snapshot`
- `result_status`
- `structured_result`
- `raw_graph_output`
- `error`
- timestamps

`structured_result` is intentionally schema-flexible in v1. Keep the final SOP
quality report shape as a TODO until that structured data is agreed.

`run_events` stores one row per replayable event. `(run_id, sequence)` is unique
and sequence numbers are monotonic per run.

Active SOP scheduling is globally unique for `(sop_id, env_key)` while status is
`pending` or `running`. Terminal runs remain queryable and do not block future
scheduling.

On service startup, leftover `pending` or `running` runs are marked
`interrupted`. V1 does not automatically resume from checkpoints.

## Components

### `AppShell`

Shared page frame with sidebar navigation and route outlet. It exposes the SOP
quality route and MCP management route without owning feature behavior.

### `ProtectedRoute`

Route guard for admin-only areas. It currently delegates to `useAuthz()` and
renders a small 403 state when access is denied. Future auth integration should
replace `useAuthz()` rather than duplicating authorization logic in pages.

### `RunObserver`

Top-level generic run observation component.

Responsibilities:

- fetch run summary with `useRun(runId)`
- subscribe to persisted SSE events with `useRunEvents`
- reduce events into node and timeline state
- render status, nodes, and event stream
- refresh the run summary after terminal `done` or `error`

### `StreamMarkdown`

Wraps `Streamdown` from the `streamdown` package. Use it for `messages` event
content and explicitly markdown event payloads. Do not use raw
`dangerouslySetInnerHTML` or a custom markdown renderer.

Tailwind scans Streamdown classes from frontend-local dependencies:

```css
@source "../../node_modules/streamdown/dist/*.js";
@import "streamdown/styles.css";
```

If dependencies are later hoisted to the repository root, update the relative
path and document the choice in `frontend/README.md`.

### `ChatPage`

SOP-specific page that composes:

- left rail with new run action and recent SOP run history
- environment selector
- SOP ID input
- run start button
- generic `RunObserver`

The page is a thin wrapper. SOP `env` is used for environment loading, run
creation, conflict join, and history APIs. It is not passed into `RunObserver`
as generic run metadata.

### `McpPage`

Operational MCP management workspace. It composes:

- top bar with page title and create action
- left panel with search, status filter, server list, and lifecycle shortcuts
- right panel with selected server status, configuration, and tools snapshot
- drawer form for create and edit flows

`McpPage` owns orchestration state such as selected server ID, active tab,
drawer state, and mutation refresh flow. Request construction stays in
`features/mcp/api.ts`; loading and mutation state stay in `features/mcp/hooks.ts`.

## UI Rules

Use the Cohere-inspired system in `DESIGN.md`.

- Prefer white and stone work surfaces with thin rules.
- Keep the observer compact and operational.
- Avoid marketing heroes, decorative gradients, ornamental backgrounds, and
  floating page-section cards.
- Use practical cards only for repeated run/event items.
- Keep radius near 8px unless a component demands otherwise.
- Use `action-blue` for links and precise secondary actions.
- Use warning/accent color sparingly.
- Ensure text fits on mobile and desktop.

## Error Handling

- Run creation `202`: observe returned `run_id`.
- Run creation `409`: observe returned `active_run_id` and show a short join
  message.
- SOP preview or start `404`: show missing SOP or environment.
- SOP preview or start `502`: show upstream SOP client failure.
- SSE reconnect: show reconnecting state without clearing previous output.
- Unknown event type: keep the observer stable and avoid crashing the page.
- MCP update `409`: show "请先停止服务再修改配置".
- MCP `404`: show a clear missing-server message and clear stale selection when
  the missing server is the selected one.
- MCP lifecycle `502` or `503`: show an operation failure message and keep the
  user on the management page.
- MCP delete and restart require confirmation before dispatch.

Frontend API errors should preserve FastAPI `detail` when the response provides
it.

## Testing

Frontend coverage should include:

- API URL construction and SOP-agnostic generic run types.
- Reducer behavior for each event type.
- SSE cursor, reconnect, and terminal handling.
- Streamdown rendering for streamed markdown.
- Run observer status, node ordering, and event stream behavior.
- SOP page behavior for environment loading, start, conflict join, recent
  history, and sidebar interactions.
- App routing for `/sop`, `/mcp`, default redirects, and protected-route
  allow/deny behavior.
- MCP API URL construction, lifecycle paths, and FastAPI `detail` propagation.
- MCP hooks for initial loading, selected detail refresh, and mutation-triggered
  refresh.
- MCP page behavior for list rendering, selection, tools tab, lifecycle actions,
  safeguards, and error messages.
- Browser smoke checks for desktop and mobile layout.

Backend coverage should include:

- public environment listing
- SOP preview without run creation
- `202` start response
- `409` duplicate active run response
- historical and recent SOP run listings
- persisted event replay through `after`
- multiple subscribers observing the same run
- default run responses omitting raw debug payloads

## Local Development

Backend:

```bash
uv sync
uv run alembic upgrade head
uv run fastapi dev
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run test
npm run build
```

Repository-local verification used by recent work:

```bash
.venv/bin/python -m pytest
cd frontend && npm run test -- --run
cd frontend && npm run build
```

DB integration tests require `TEST_DATABASE_URL` and a local Postgres instance.

## Open Decisions

- Final structured SOP quality report schema.
- Authentication and authorization rules for `debug=true`.
- Real administrator authorization and how the MCP admin token reaches the
  frontend request layer.
- Whether `created_by` comes from auth middleware, headers, or a future user
  table.
- Exact graph node list and whether node registries come from backend metadata.
- Whether to add Streamdown plugins such as code, math, or mermaid support.
- Real SOP client implementation and dependency wiring.
- Whether a future worker or LangGraph Server migration replaces the in-process
  v1 runner.

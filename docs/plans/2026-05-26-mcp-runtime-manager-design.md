# MCP Runtime Manager Backend Design

Date: 2026-05-26

## Context

Change Quality Agent currently provides a FastAPI + LangGraph backend for SOP
quality runs. The frontend will later include an integrated MCP management page,
but the first implementation step is the backend substrate.

The MCP backend should let users register MCP servers, manage their desired
runtime state, inspect current status, and discover available tools. This design
uses Postgres as the durable source of truth and a FastAPI in-process runtime
manager as the owner of live MCP stdio sessions.

## Goals

- Store MCP server configuration in the database.
- Support list, detail, create, update, delete, start, stop, restart, and check
  operations through versioned HTTP APIs.
- Manage stdio MCP server processes from the backend runtime manager.
- Discover tools through MCP initialization and `tools/list`.
- Persist the latest successful tool snapshot for each server.
- Preserve a clear boundary between MCP management and LangGraph agent runs.
- Prepare a clean integration path for future ReAct agent configuration.

## Non-Goals

- Do not connect MCP tools to SOP quality runs in the first version.
- Do not design the frontend page in this backend plan.
- Do not support remote HTTP MCP lifecycle management yet.
- Do not support multiple FastAPI workers coordinating the same live server.
- Do not persist full stdout or stderr logs.
- Do not copy MCP command, args, or env into future ReAct agent tables.

## Key Decisions

- Use a runtime manager, not a config-only registry.
- Store MCP server config and runtime snapshots in `mcp_servers`.
- Store the latest successful tool discovery result in `mcp_server_tools`.
- Support `stdio` and `http` in the schema, but implement lifecycle only for
  `stdio` in v1.
- Treat `enabled`, `desired_state`, and `runtime_status` as separate concepts.
- Require callers to stop a running server before editing its config.
- Redact secret-like config values from API responses.
- Make MCP Runtime Manager the only owner of live MCP processes and sessions.

## Architecture

The MCP feature is a separate backend domain:

- `app/api/v1/mcp.py` exposes MCP management endpoints.
- `app/schemas/mcp.py` defines request and response models.
- `app/models/mcp.py` defines SQLAlchemy models.
- `app/repositories/mcp_servers.py` handles persistence and tool snapshots.
- `app/services/mcp_runtime.py` owns lifecycle, process handles, and status
  transitions.
- `app/api/deps.py` exposes repository and runtime dependencies.
- `app/main.py` initializes and shuts down the runtime manager in lifespan.
- `api/openapi.yml` documents the shared API contract.

FastAPI routes should validate HTTP input, call the service layer, and shape
responses. They should not spawn MCP processes directly. The runtime service
should not know about SOP-specific workflows or future ReAct agent CRUD.

## Database Design

### `mcp_servers`

`mcp_servers` stores durable configuration and the latest runtime snapshot.

Suggested fields:

- `id UUID PRIMARY KEY`
- `name TEXT NOT NULL UNIQUE`
- `transport TEXT NOT NULL`
- `command TEXT`
- `args JSONB NOT NULL DEFAULT '[]'`
- `env JSONB NOT NULL DEFAULT '{}'`
- `url TEXT`
- `headers JSONB NOT NULL DEFAULT '{}'`
- `enabled BOOLEAN NOT NULL DEFAULT FALSE`
- `desired_state TEXT NOT NULL DEFAULT 'stopped'`
- `runtime_status TEXT NOT NULL DEFAULT 'unknown'`
- `last_checked_at TIMESTAMPTZ`
- `last_error TEXT`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`

Validation rules:

- `transport` is `stdio` or `http`.
- `stdio` servers require `command`.
- `http` servers require `url`, but lifecycle returns unsupported in v1.
- `desired_state` is `running` or `stopped`.
- `runtime_status` is `unknown`, `starting`, `running`, `stopping`, `stopped`,
  or `error`.

### `mcp_server_tools`

`mcp_server_tools` stores the latest successful tool discovery snapshot.

Suggested fields:

- `id UUID PRIMARY KEY`
- `server_id UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE`
- `name TEXT NOT NULL`
- `description TEXT`
- `input_schema JSONB NOT NULL DEFAULT '{}'`
- `discovered_at TIMESTAMPTZ NOT NULL`

Suggested indexes:

- `(server_id, name)` unique
- `(server_id)`

Tool snapshots are replaced as a set after successful discovery. Failed checks
do not delete the previous successful snapshot.

## API Design

### Server Collection

`GET /api/mcp/servers`

Returns all MCP servers with redacted configuration, current runtime status, and
tool count.

`POST /api/mcp/servers`

Creates a server config. The request accepts full config values, including env
and headers. The response redacts sensitive values.

### Server Detail

`GET /api/mcp/servers/{server_id}`

Returns one server with redacted config and the latest tool snapshot.

`PATCH /api/mcp/servers/{server_id}`

Updates config and display fields. If the server is currently running, return
`409 Conflict` and require callers to stop it first.

`DELETE /api/mcp/servers/{server_id}`

Deletes a server. If it is running, the API attempts to stop it first. If stop
fails, the delete fails and the config remains.

### Lifecycle

`POST /api/mcp/servers/{server_id}/start`

Sets `desired_state` to `running` and attempts to start the server. If already
running, returns the current status.

`POST /api/mcp/servers/{server_id}/stop`

Sets `desired_state` to `stopped` and attempts to stop the server. Stop is
idempotent.

`POST /api/mcp/servers/{server_id}/restart`

Stops and starts the server. The final `desired_state` is `running`.

`POST /api/mcp/servers/{server_id}/check`

Does not change `desired_state`. If the server is running, it reuses the live
session to refresh tools. If the server is stopped, it starts a temporary MCP
session, discovers tools, updates status fields, and closes the temporary
session.

All lifecycle responses return a structured status object with `server_id`,
`desired_state`, `runtime_status`, `last_checked_at`, `last_error`, and
`tool_count`.

## Runtime Lifecycle

`McpRuntimeManager` is created during FastAPI lifespan. On startup, it loads
servers where `enabled=true AND desired_state='running'` and attempts to start
them. On shutdown, it closes all live sessions and terminates child processes.

The manager keeps an in-memory map:

```text
server_id -> runtime handle
```

The database remains the durable source for configuration and user-visible
runtime snapshots. In-memory handles are not expected to survive process
restart.

State transitions are intentionally small:

```text
unknown -> starting -> running
unknown -> starting -> error
running -> stopping -> stopped
running -> error
stopped -> starting
error -> starting
```

`start` flow:

1. Load server config.
2. Validate transport and stdio command policy.
3. If already running, return current status.
4. Set `runtime_status='starting'`.
5. Start child process and initialize MCP session.
6. Call `tools/list`.
7. Replace the tool snapshot.
8. Set `runtime_status='running'` and clear `last_error`.

`stop` flow:

1. Set `runtime_status='stopping'`.
2. Close the MCP session if present.
3. Terminate the child process.
4. Escalate to force termination after timeout.
5. Set `runtime_status='stopped'`.

## ReAct Agent Integration Boundary

Future ReAct agent CRUD should store agent blueprints and references to MCP
servers. It should not store MCP process config or instantiate MCP sessions.

Future agent tables should reference `mcp_servers.id` and define:

- Which MCP servers an agent may use.
- Whether a run may auto-start a referenced MCP server.
- Tool allowlists or denylists.
- Tool aliases and description overrides.
- Permission policy for tool use.

Agent instantiation happens at run creation time:

```text
load react agent config
-> resolve referenced MCP servers
-> ensure servers are running, if policy allows
-> read latest tools snapshot or live tools/list
-> apply agent-level tool filters
-> namespace tools by server
-> wrap MCP tools as agent-callable tools
-> instantiate the ReAct graph
-> record the resolved MCP/tool snapshot in run metadata
```

Tools should be namespaced to avoid collisions:

```text
{server_name}.{tool_name}
```

MCP servers are shared runtime resources. ReAct agents are consumers assembled
from durable blueprints at run time.

## Error Handling

Lifecycle APIs should return useful state, not only success or failure.

Startup failure:

- Keep `desired_state='running'`.
- Set `runtime_status='error'`.
- Store a short `last_error`.
- Preserve the previous successful tool snapshot.

Check failure:

- Do not change `desired_state`.
- Update `last_checked_at`.
- Store `last_error`.
- Preserve the previous successful tool snapshot.

Unsupported transport:

- Allow HTTP configs to be stored.
- Return a clear unsupported-transport error for start, restart, and check in
  v1.

Missing live handle:

- If the database says running but no handle exists, treat the server as not
  running in the current process and reconcile status during the next lifecycle
  operation.

## Security

The stdio configuration must avoid shell execution.

- Accept `command` and `args` as separate fields.
- Do not accept a shell command string.
- Validate command against an allowlist or trusted absolute path policy.
- Redact `env` and `headers` values in responses.
- Store only short error summaries, not full stdout or stderr.
- Avoid logging request bodies that may contain secrets.

First version should at least provide response redaction. Database encryption
for secret fields can be a separate security enhancement.

## Testing Strategy

Repository and model tests:

- CRUD behavior.
- Name uniqueness.
- Status field updates.
- Tool snapshot replacement.
- Tool cascade delete.

API tests:

- Server list, detail, create, update, delete.
- Start, stop, restart, and check responses.
- `409 Conflict` when editing a running server.
- Redaction of `env` and `headers`.
- Unsupported HTTP lifecycle behavior.

Runtime unit tests:

- Use fake transport or fake MCP client for the state machine.
- Cover start success, initialize failure, tools/list failure, idempotent stop,
  and restart sequencing.

Integration tests:

- Use a project-local stub stdio MCP server for a small number of protocol-level
  tests.
- Avoid network dependencies and third-party MCP servers in the default test
  suite.

Lifespan tests:

- Verify startup attempts to run enabled servers with desired state `running`.
- Verify shutdown cleans up runtime handles.
- Use fake runtime manager where possible to avoid leaked subprocesses.

## First Version Scope

Included:

- Database-backed MCP server registry.
- Stdio lifecycle management.
- Tool discovery and latest snapshot persistence.
- API-level redaction.
- Lifespan startup and shutdown integration.
- HTTP transport schema reservation.

Deferred:

- HTTP MCP lifecycle.
- Cross-worker runtime coordination.
- Runtime log streaming.
- Full stdout or stderr persistence.
- ReAct agent tables and APIs.
- SOP agent use of MCP tools.
- Secret encryption at rest.

The first version succeeds when a user can register a stdio MCP server, start
it, inspect its status, refresh its tools, stop it, and have the backend restore
the desired running servers after application restart.

## Open Questions

- Which stdio commands should be allowed by default?
- Should secret fields be encrypted in the first implementation or a follow-up?
- Should `check` update `runtime_status` for stopped servers after a successful
  temporary probe, or only `last_checked_at` and tools?
- Should restart be exposed as a separate operation or implemented by the
  frontend as stop then start?

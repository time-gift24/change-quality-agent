# ReAct Agent CRUD Design

Date: 2026-05-26

## Context

This project already has a generic run substrate built around `runs` and
`run_events`. SOP quality checking is the first workflow, but the run model is
intentionally subject-agnostic. The ReAct agent feature should build on that
substrate instead of creating a separate execution history model.

The product direction is to let users define ReAct agents, publish immutable
versions, test them through the same run observation APIs, and later use a
published agent version as a dynamic LangGraph node. Tool management, MCP
server management, and LLM provider configuration will be owned by separate
modules. This design stores only references to those future resources.

The runtime should use `langchain.agents.create_agent` directly, but the API and
database should store plain JSON configuration rather than LangChain-specific
objects.

## Goals

- Provide backend CRUD APIs for ReAct agent definitions.
- Support draft editing and immutable published versions.
- Default test runs to the latest published version while allowing explicit
  historical version selection.
- Execute test runs through the existing `runs` and `run_events` substrate.
- Keep tools, MCP servers, and LLM providers as referenced external modules.
- Leave a clean path for published agent versions to become dynamic nodes later.

## Non-Goals

- Do not build the React frontend in this phase.
- Do not build tool CRUD, MCP server management, or LLM provider management.
- Do not validate tool IDs or MCP server IDs against real registries in MVP.
- Do not implement dynamic graph node composition in MVP.
- Do not implement auth, workspace scoping, or sharing rules in MVP.
- Do not implement LangGraph checkpoint resume for agent tests in MVP.
- Do not implement token-level streaming in MVP.

## Key Decisions

- Use `key` as the stable human-readable agent identifier.
- Keep `display_name` separate from `key` for UI display.
- Use draft editing plus explicit publish.
- Create a new immutable `agent_versions` row on every publish.
- Store `model` as a string and `model_config` as JSON.
- Store `tool_allowlist` and `mcp_server_ids` as string references only.
- Use soft delete for agents.
- Test runs use the existing generic run APIs and SSE events.
- Runtime implementation calls `langchain.agents.create_agent`.

## Architecture

The feature has four backend boundaries:

1. `app/api/v1/agents.py`
   - Defines HTTP endpoints.
   - Validates request parameters and request bodies.
   - Shapes responses with Pydantic schemas.
   - Does not contain LangChain or LangGraph business logic.

2. `app/services/agents.py`
   - Coordinates agent creation, draft updates, publishing, soft delete, and
     test run scheduling.
   - Owns business rules such as "no test run without a published version".
   - Creates `runs` rows for test runs and schedules background execution.

3. `app/repositories/agents.py`
   - Encapsulates SQLAlchemy persistence for `agents` and `agent_versions`.
   - Locks an agent row while publishing so version numbers stay monotonic.
   - Keeps soft-deleted agents queryable for historical references.

4. `agent/react_runtime.py`
   - Adapts a published agent version into a runnable LangChain agent.
   - Calls `langchain.agents.create_agent`.
   - Resolves tool and MCP references through replaceable resolver interfaces.
   - Returns normalized results that the service persists to `runs` and
     `run_events`.

This keeps the web API layer, persistence layer, and agent runtime layer
separate. Later dynamic node support should reuse the published version model
and runtime boundary instead of introducing a second agent definition format.

## API Design

All routes use the `agents` tag and live under `/api/agents`.

### Create Agent

`POST /api/agents`

Creates an agent and stores the initial draft. It does not publish a runnable
version.

Request:

```json
{
  "key": "release-reviewer",
  "display_name": "Release Reviewer",
  "description": "Checks release change quality",
  "draft": {
    "system_prompt": "You are a careful release reviewer.",
    "model": "openai:gpt-5-mini",
    "model_config": {"temperature": 0},
    "tool_allowlist": ["search_sop", "read_change"],
    "mcp_server_ids": ["change-docs"]
  }
}
```

Responses:

- `201 Created` with `AgentDetail`.
- `409 Conflict` when `key` already exists.
- `422 Unprocessable Entity` for malformed input.

### List Agents

`GET /api/agents?include_deleted=false`

Returns agents ordered by creation time or display name. The default response
hides soft-deleted agents. Each item includes latest published version summary
and whether a draft exists.

### Get Agent

`GET /api/agents/{agent_key}`

Returns agent details, current draft, and latest published version summary.
Soft-deleted agents should return `404` by default unless a future debug or
admin mode explicitly includes them.

### Update Draft

`PATCH /api/agents/{agent_key}/draft`

Updates editable metadata and draft configuration. This does not create a new
published version.

Editable fields:

- `display_name`
- `description`
- `enabled`
- `draft.system_prompt`
- `draft.model`
- `draft.model_config`
- `draft.tool_allowlist`
- `draft.mcp_server_ids`

### Publish Version

`POST /api/agents/{agent_key}/publish`

Creates an immutable version from the current draft and updates the agent's
`latest_version_id`.

Responses:

- `201 Created` with `AgentVersionDetail`.
- `400 Bad Request` if there is no draft or the draft lacks required runtime
  fields.
- `404 Not Found` if the agent does not exist or is deleted.
- `409 Conflict` if a concurrent publish cannot be resolved cleanly.

### List Versions

`GET /api/agents/{agent_key}/versions`

Returns published versions ordered by `version_number` descending.

### Get Version

`GET /api/agents/{agent_key}/versions/{version_number}`

Returns an immutable published version.

### Start Test Run

`POST /api/agents/{agent_key}/test-runs`

Starts a background test run. The request defaults to the latest published
version. It may specify `version_id` or `version_number` for reproducibility.

Request:

```json
{
  "version_number": 3,
  "messages": [
    {"role": "user", "content": "Review this change for release risk."}
  ]
}
```

Response reuses `RunStartResponse`:

```json
{
  "run_id": "uuid",
  "status": "pending",
  "status_url": "/api/runs/uuid",
  "events_url": "/api/runs/uuid/events"
}
```

Clients observe execution through the existing generic endpoints:

- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events?after=0`

### Delete Agent

`DELETE /api/agents/{agent_key}`

Soft deletes the agent by setting `deleted_at`. Historical versions and runs
remain queryable. The key is not released for reuse.

## Schema Design

Suggested Pydantic schemas:

- `AgentDraftConfig`
- `AgentCreate`
- `AgentDraftUpdate`
- `AgentSummary`
- `AgentDetail`
- `AgentVersionSummary`
- `AgentVersionDetail`
- `AgentPublishResponse`
- `AgentTestRunCreate`

`AgentDraftConfig`:

```json
{
  "system_prompt": "string",
  "model": "provider:model",
  "model_config": {},
  "tool_allowlist": ["string"],
  "mcp_server_ids": ["string"]
}
```

`AgentTestRunCreate.messages` should use a small explicit message schema:

```json
{
  "role": "user",
  "content": "Review this change."
}
```

Allowed roles in MVP should be the roles accepted by the runtime adapter, at
least `user`, `assistant`, and `system` if `create_agent` usage permits it. The
service should prefer putting the configured system prompt in the published
version rather than requiring callers to send a system message.

## Database Design

### `agents`

`agents` stores stable identity and editable draft state.

Suggested fields:

- `id UUID PRIMARY KEY`
- `key TEXT NOT NULL UNIQUE`
- `display_name TEXT NOT NULL`
- `description TEXT`
- `enabled BOOLEAN NOT NULL DEFAULT TRUE`
- `draft_config JSONB`
- `latest_version_id UUID NULL`
- `created_by TEXT`
- `updated_by TEXT`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`
- `deleted_at TIMESTAMPTZ`

The `latest_version_id` should reference `agent_versions(id)`. If the migration
tooling has trouble with the circular reference at creation time, add the
foreign key after both tables exist.

`draft_config` stores the editable configuration:

```json
{
  "system_prompt": "You are a careful reviewer.",
  "model": "openai:gpt-5-mini",
  "model_config": {"temperature": 0},
  "tool_allowlist": ["search_sop"],
  "mcp_server_ids": ["change-docs"]
}
```

### `agent_versions`

`agent_versions` stores immutable runnable configuration.

Suggested fields:

- `id UUID PRIMARY KEY`
- `agent_id UUID NOT NULL REFERENCES agents(id)`
- `version_number INTEGER NOT NULL`
- `system_prompt TEXT NOT NULL`
- `model TEXT NOT NULL`
- `model_config JSONB NOT NULL DEFAULT '{}'`
- `tool_allowlist JSONB NOT NULL DEFAULT '[]'`
- `mcp_server_ids JSONB NOT NULL DEFAULT '[]'`
- `published_by TEXT`
- `published_at TIMESTAMPTZ NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`

Constraints and indexes:

```sql
CREATE UNIQUE INDEX uq_agents_key ON agents (key);
CREATE UNIQUE INDEX uq_agent_versions_agent_version
ON agent_versions (agent_id, version_number);
CREATE INDEX ix_agent_versions_agent_published
ON agent_versions (agent_id, published_at DESC);
```

Publishing should happen in a transaction:

1. Lock the `agents` row with `SELECT ... FOR UPDATE`.
2. Validate the draft.
3. Compute `next_version_number`.
4. Insert `agent_versions`.
5. Update `agents.latest_version_id`.
6. Commit.

Soft delete should not release `agents.key`, because historical runs use the key
as a readable subject identifier.

## Run Integration

Agent test runs use the existing `runs` table:

- `assistant_id = "react-agent-test-v1"`
- `subject_type = "agent_test"`
- `subject_id = agent.key`
- `env_key = NULL`
- `active_conflict_key = NULL`
- `status = "pending"`
- `completed_nodes = []`

Test runs should not be mutually exclusive. Multiple tests for the same agent
version may run concurrently.

`runs.metadata` should include:

```json
{
  "subject_type": "agent_test",
  "subject_id": "release-reviewer",
  "agent_id": "uuid",
  "agent_key": "release-reviewer",
  "agent_version_id": "uuid",
  "agent_version_number": 3,
  "run_kind": "agent_test",
  "input_preview": "Review this change for release risk."
}
```

`runs.subject_snapshot` should include the input and a runtime configuration
summary:

```json
{
  "messages": [
    {"role": "user", "content": "Review this change for release risk."}
  ],
  "agent_version": {
    "id": "uuid",
    "version_number": 3,
    "model": "openai:gpt-5-mini",
    "tool_allowlist": ["search_sop"],
    "mcp_server_ids": ["change-docs"]
  }
}
```

The full system prompt may be persisted for internal traceability, but it
should not be exposed through default run summary responses. Future auth and
debug policy should decide whether prompt content appears in public responses.

## Runtime Flow

The test run flow is:

1. `POST /api/agents/{agent_key}/test-runs`.
2. The service validates that the agent exists, is enabled, and is not deleted.
3. The service chooses the requested version or the latest published version.
4. The service creates a `runs` row and commits.
5. A background task starts execution after commit.
6. The executor marks the run `running`.
7. The executor appends a `custom` event describing the selected agent version.
8. The runtime resolves tool and MCP references through injected resolvers.
9. The runtime calls `langchain.agents.create_agent`.
10. The runtime invokes the agent with the request messages.
11. Success appends `messages` and `done` events, then marks the run `success`.
12. Failure appends an `error` event, then marks the run `error`.

Suggested runtime interfaces:

```python
class ToolResolver:
    async def resolve(
        self,
        tool_allowlist: list[str],
        mcp_server_ids: list[str],
    ) -> list[object]:
        ...


class AgentRuntime:
    async def run(
        self,
        *,
        version: AgentVersion,
        messages: list[dict[str, str]],
    ) -> AgentRunResult:
        ...
```

MVP resolvers may return an empty tool list or a hard-coded subset. The
resolver boundary exists so the future tool and MCP modules can take over
without changing the Agent CRUD API.

## Event Contract

Agent test events should use the existing durable event envelope. MVP only
needs coarse events:

- `custom`: run started, tool/MCP reference summary.
- `messages`: final assistant message or stable message output.
- `done`: successful completion.
- `error`: runtime or model failure.

Future enhancements can add token chunks, tool call events, and checkpoint
pointers without changing the start-test-run API.

## Error Handling

Before a run exists, errors should return HTTP responses:

- `400 Bad Request`: no draft to publish, invalid draft, no published version
  for test run, or disabled agent test request.
- `404 Not Found`: unknown or soft-deleted agent.
- `409 Conflict`: duplicate key or unresolved concurrent publish conflict.
- `422 Unprocessable Entity`: malformed request body.

After a run exists, execution failures should be persisted:

- Append `run_events.type = "error"`.
- Set `runs.status = "error"`.
- Set `runs.error = {"type": "...", "message": "..."}`.
- Set `runs.result_status = "error"`.

The test-run creation endpoint should not become `500` for model, tool, MCP, or
runtime failures that happen after scheduling.

## Testing Strategy

API tests:

- Creating an agent stores draft configuration.
- Duplicate agent keys return `409`.
- Listing agents hides soft-deleted agents by default.
- Fetching a soft-deleted agent returns `404`.
- Updating draft does not create a version.
- Publishing creates version `1` and updates latest version.
- Publishing again creates version `2`.
- Publishing without a valid draft returns `400`.
- Test run defaults to the latest published version.
- Test run accepts an explicit historical version.
- Test run without any published version returns `400`.
- Soft-deleted agents cannot start test runs.

Persistence tests:

- `agents.key` is unique.
- `agent_versions(agent_id, version_number)` is unique.
- Publish version numbers are monotonic.
- Soft delete preserves versions.
- Soft delete does not release the key.

Service and runtime tests:

- The agent service creates `runs` with `subject_type = "agent_test"`.
- The scheduler runs only after the run row is committed.
- A fake runtime success writes start, message, and done events.
- A fake runtime failure writes an error event and marks the run `error`.
- The runtime adapter passes `model`, `system_prompt`, resolved tools, and
  messages into the `create_agent` boundary.
- Tool and MCP resolver dependencies can be replaced in tests.

Contract tests:

- `api/openapi.yml` includes the new `agents` tag, paths, and schemas.
- FastAPI response models match the OpenAPI contract.

## Open Decisions

- Exact format of model strings after the LLM provider module exists.
- Whether disabled agents should return `400` or `409` for test run attempts.
- Whether prompt content is available through future debug responses.
- How frontend draft conflict detection should work, such as `updated_at`
  optimistic concurrency or last-write-wins.
- How future tool and MCP modules report missing references at runtime.

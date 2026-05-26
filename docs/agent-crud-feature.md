# ReAct Agent CRUD Feature

Date: 2026-05-26

## Purpose

The ReAct Agent CRUD feature adds a backend agent registry for defining,
publishing, and test-running ReAct agents. It builds on the existing generic
`runs` and `run_events` substrate so agent execution can be observed through the
same run APIs already used by SOP quality runs.

The feature is intentionally limited to agent definition and test execution.
Tool management, MCP server management, and LLM provider configuration remain
separate modules. This feature stores references to those future resources
instead of owning them directly.

## Core Capabilities

- Create, list, read, update, and soft-delete ReAct agent definitions.
- Store editable draft configuration on the `agents` row.
- Publish immutable runnable snapshots into `agent_versions`.
- Keep published version numbers monotonic per agent.
- Start background ReAct agent test runs from the latest published version or
  an explicitly selected historical version.
- Persist test-run status, events, errors, and raw runtime output through the
  existing `runs` and `run_events` tables.
- Wrap `langchain.agents.create_agent` behind `agent/react_runtime.py` so future
  dynamic-node, tool, and MCP integrations can reuse the same runtime boundary.

## API Surface

All agent routes live under `/api/agents` and use the OpenAPI `agents` tag.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/agents` | Create an agent with an initial draft. |
| `GET` | `/api/agents` | List agents, hiding soft-deleted agents by default. |
| `GET` | `/api/agents/{agent_key}` | Fetch agent details, draft, and latest published version. |
| `PATCH` | `/api/agents/{agent_key}/draft` | Update metadata, enabled state, or draft config. |
| `POST` | `/api/agents/{agent_key}/publish` | Publish the current draft as a new immutable version. |
| `GET` | `/api/agents/{agent_key}/versions` | List published versions. |
| `GET` | `/api/agents/{agent_key}/versions/{version_number}` | Fetch one published version. |
| `POST` | `/api/agents/{agent_key}/test-runs` | Start a background ReAct agent test run. |
| `DELETE` | `/api/agents/{agent_key}` | Soft-delete the agent while preserving history. |

Test-run creation returns the shared `RunStartResponse`, including `run_id`,
`status_url`, and `events_url`. Clients observe execution through:

- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events?after=0`

## Agent Configuration

An agent draft stores the editable runtime configuration:

```json
{
  "system_prompt": "You are a careful release reviewer.",
  "model": "openai:gpt-5-mini",
  "model_config": {"temperature": 0},
  "tool_allowlist": ["search_sop", "read_change"],
  "mcp_server_ids": ["change-docs"]
}
```

Published versions copy the draft into immutable fields:

- `system_prompt`
- `model`
- `model_config`
- `tool_allowlist`
- `mcp_server_ids`

The API exposes the JSON key `model_config`. Internally, Pydantic schemas avoid
the `BaseModel.model_config` naming collision by mapping that external field to
an internal `model_parameters` attribute where needed.

## Persistence Model

`agents` stores stable identity and editable draft state:

- `id`
- `key`
- `display_name`
- `description`
- `enabled`
- `draft_config`
- `latest_version_id`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`
- `deleted_at`

`agent_versions` stores immutable runnable snapshots:

- `id`
- `agent_id`
- `version_number`
- `system_prompt`
- `model`
- `model_config`
- `tool_allowlist`
- `mcp_server_ids`
- `published_by`
- `published_at`
- `created_at`

Important constraints:

- `agents.key` is unique and is not released by soft delete.
- `(agent_versions.agent_id, agent_versions.version_number)` is unique.
- Publishing locks the agent row before computing the next version number.
- `agents.latest_version_id` points at the most recently published version.

## Test Run Integration

Agent test runs reuse the generic run model with these values:

- `assistant_id = "react-agent-test-v1"`
- `subject_type = "agent_test"`
- `subject_id = agent.key`
- `env_key = null`
- `active_conflict_key = null`

Unlike SOP runs, agent test runs are not mutually exclusive. Multiple tests for
the same agent or version may run concurrently.

Run metadata includes the selected agent and version:

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

`subject_snapshot` stores the input messages and a summary of the selected
runtime configuration.

## Runtime Flow

The test-run flow is:

1. The client calls `POST /api/agents/{agent_key}/test-runs`.
2. The service verifies that the agent exists, is enabled, and has a published
   version.
3. The service selects the requested version or defaults to the latest
   published version.
4. A `runs` row is created and committed before execution starts.
5. A background task loads the run and version in a fresh session.
6. The run is marked `running`.
7. A start event is appended.
8. `AgentRuntime` resolves tools through the configured resolver.
9. `AgentRuntime` builds a model with `langchain.chat_models.init_chat_model`.
10. `AgentRuntime` calls `langchain.agents.create_agent`.
11. The runtime invokes the agent with the request messages.
12. Success appends message and done events, stores normalized output, and marks
    the run `success`.
13. Failure appends an error event, stores error details, and marks the run
    `error`.

The default tool resolver returns no tools. That placeholder keeps this feature
independent from the later hard-coded tool registry and MCP server manager.

## Event Contract

Agent test runs use the existing durable event envelope. The MVP emits coarse
events only:

- `custom`: start and runtime-selection summaries.
- `messages`: final message output.
- `done`: successful completion.
- `error`: runtime, model, tool, or missing-version failure.

Future enhancements can add token chunks, tool-call events, checkpoint IDs, or
dynamic-node events without changing the start-test-run API.

## Error Semantics

Before a run exists, request errors are HTTP responses:

- `400 Bad Request`: invalid draft publish, disabled agent, missing published
  version, or invalid requested version.
- `404 Not Found`: unknown or soft-deleted agent.
- `409 Conflict`: duplicate agent key.
- `422 Unprocessable Entity`: malformed request body or path parameter.

After a run exists, runtime failures are persisted on the run:

- append a `run_events.type = "error"` event.
- set `runs.status = "error"`.
- set `runs.error`.
- set `runs.result_status = "error"`.

The start-test-run endpoint should not turn post-scheduling runtime failures
into HTTP `500` responses.

## Deferred Work

This feature deliberately does not include:

- React frontend screens.
- Tool CRUD or real tool registry validation.
- MCP server CRUD or real MCP server validation.
- LLM provider configuration UI or provider-specific policy.
- Dynamic LangGraph node composition.
- Auth, workspace scoping, sharing, or per-agent permissions.
- Token-level streaming.
- LangGraph checkpoint resume for agent tests.

# ReAct Agent CRUD Feature

Date: 2026-05-26

## Purpose

The ReAct Agent CRUD feature adds a backend agent registry for defining and
publishing ReAct agents. It owns agent metadata, editable drafts, immutable
published versions, and model runtime configuration. Agent execution observation
is no longer exposed through the removed generic run APIs.

Tool management, MCP server management, LLM provider configuration, and SOP
quality checks remain separate modules. Agent versions may reference stored LLM
providers by id, but they do not own provider credentials.

## Core Capabilities

- Create, list, read, update, and soft-delete ReAct agent definitions.
- Store editable draft configuration on the `agents` row.
- Publish immutable runnable snapshots into `agent_versions`.
- Keep published version numbers monotonic per agent.
- Resolve model runtime configuration from either `codeagent:` model names or
  stored LLM providers.

## API Surface

All agent routes live under `/api/agents` and use the OpenAPI `agents` tag.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/agents` | Create an agent with an initial draft. |
| `GET` | `/api/agents` | List agents, hiding soft-deleted agents by default. |
| `GET` | `/api/agents/{agent_id}` | Fetch agent details, draft, and latest published version. |
| `PATCH` | `/api/agents/{agent_id}/draft` | Update metadata, enabled state, or draft config. |
| `POST` | `/api/agents/{agent_id}/publish` | Publish the current draft as a new immutable version. |
| `GET` | `/api/agents/{agent_id}/versions` | List published versions. |
| `GET` | `/api/agents/{agent_id}/versions/{version_number}` | Fetch one published version. |
| `DELETE` | `/api/agents/{agent_id}` | Soft-delete the agent while preserving history. |

## Agent Configuration

An agent draft stores editable runtime configuration:

```json
{
  "system_prompt": "你是谨慎的发布评审助手。请识别发布风险、审批缺口和可执行的整改建议。",
  "model": "gpt-5-mini",
  "provider_id": "00000000-0000-0000-0000-000000000000",
  "model_config": {
    "temperature": 0,
    "reasoning_effort": "high",
    "model_kwargs": {
      "stream_options": {"include_usage": true}
    }
  },
  "tool_allowlist": ["search_sop", "read_change"],
  "mcp_server_ids": ["change-docs"]
}
```

Published versions copy the draft into immutable fields:

- `system_prompt`
- `model`
- `provider_id`
- `model_config`
- `tool_allowlist`
- `mcp_server_ids`

`provider_id` and prefixed model names are mutually exclusive:

- `model = "codeagent:deepseek-v4-pro"` uses the internal CodeAgent factory and
  must not set `provider_id`.
- `provider_id = "<uuid>"` requires a bare model name such as `gpt-5-mini`.

## Data Model

`agents` stores mutable registry state:

- `id`: stable UUID public identifier.
- `display_name`: user-visible name.
- `description`: optional summary.
- `enabled`: disables runtime use without deleting the definition.
- `draft_config`: JSON draft payload.
- `latest_version_id`: nullable pointer to the newest published version.
- `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`.

`agent_versions` stores immutable published snapshots:

- `id`, `agent_id`, `version_number`.
- `system_prompt`, `model`, `provider_id`, `model_config`.
- `tool_allowlist`, `mcp_server_ids`.
- `published_by`, `published_at`, `created_at`.

The database enforces unique `(agent_id, version_number)` pairs.

## Runtime Boundary

`AgentRuntime` loads an `AgentVersion` and resolves its model:

1. If `provider_id` is set, the runtime loads the stored provider configuration
   and calls `langchain.chat_models.init_chat_model`.
2. If the model starts with `codeagent:`, the runtime uses the internal
   CodeAgent DeepSeek-compatible factory.
3. Otherwise, the runtime falls back to LangChain model initialization by model
   name.

The runtime currently receives tools through an injected resolver. That keeps
agent publication independent from the MCP server manager and future tool
registry work.

## Error Semantics

Agent CRUD APIs use ordinary HTTP errors:

- `400 Bad Request`: draft is invalid and cannot be published.
- `404 Not Found`: unknown or soft-deleted agent, or unknown version.
- `422 Unprocessable Entity`: malformed request body or path parameter.

Provider-backed runtime failures are not part of the CRUD API surface. Provider
connectivity is tested through `/api/v1/llm-providers/{provider_id}/test`.

## Deferred Work

- React frontend screens for agent CRUD.
- Tool CRUD and real tool registry validation.
- Runtime execution endpoints for agents, if a concrete product flow needs
  them.
- Dynamic LangGraph node composition.

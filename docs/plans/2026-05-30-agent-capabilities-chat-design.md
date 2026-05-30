# Agent Capabilities and Multi-turn Chat Design

Date: 2026-05-30

## Goal

Complete the Agent management flow so an admin can configure a draft Agent with built-in tools and MCP capabilities, save it, and immediately test the saved draft in a normal multi-turn chat page.

The first implementation should favor a simple, explicit design:

- Draft Agents can run without publishing a version.
- Built-in tools are exposed from a backend capability list, currently backed by a simple in-code list.
- MCP capabilities are selected from configured MCP servers.
- Agent chat reuses the existing shared `sessions/messages` transcript and session SSE stream.

## Non-goals

- Do not require publish/version selection before chat.
- Do not build a complex JSON inspector for tool messages.
- Do not auto-start MCP servers from the Agent chat flow.
- Do not add a second transcript model separate from `sessions/messages`.

## Backend API

### `GET /api/agents/capabilities`

Returns the capabilities that can be attached to an Agent draft.

Response shape:

```ts
{
  builtin_tools: Array<{
    name: string;
    label: string;
    description: string | null;
    enabled: boolean;
  }>;
  mcp_servers: Array<{
    id: string;
    name: string;
    enabled: boolean;
    runtime_status: string;
    tool_count: number;
  }>;
}
```

The built-in tool list should live in backend code in one shared place, for example `app/core/agent_tools.py` or `app/services/agent_capabilities.py`. The API and runtime should use the same registry so the frontend does not hard-code tool names.

### Existing Agent draft endpoints

`POST /api/agents` and `PATCH /api/agents/{agent_id}/draft` keep their current semantics, but the frontend must now send the selected values for:

- `draft.tool_allowlist`
- `draft.mcp_server_ids`

The form must no longer force both arrays to `[]`.

### `POST /api/agents/{agent_id}/sessions`

Starts or continues a chat run using the current Agent draft.

Request shape:

```ts
{
  message: string;
  session_id?: number | null;
}
```

Response shape:

```ts
{
  session_id: number;
  stream_url: string;
}
```

Semantics:

- If `session_id` is omitted, create a new session, write the user message, and start one Agent run.
- If `session_id` is present, verify that the session belongs to this Agent, append the user message, and start the next Agent run.
- The response stream URL points at the existing session stream endpoint: `/api/sessions/{id}/stream?after=...`.
- The durable transcript remains in `sessions/messages`.

## Runtime behavior

For each Agent chat run, the backend should:

1. Load the Agent and current draft.
2. Validate that the Agent is enabled and the draft has a model and system prompt.
3. Build the chat model from `provider_id`, `model`, and `model_config`.
4. Resolve built-in tools from `tool_allowlist` using the shared built-in tool registry.
5. Resolve MCP tools from `mcp_server_ids` using configured MCP servers.
6. Run the ReAct Agent with the session history plus the new user message.
7. Write assistant and tool messages to `messages` and emit them through session streaming.
8. Emit `completed` on success or `failed` on failure.

Error handling:

- Disabled Agent: return `400`.
- Missing or incomplete draft: return `400`.
- Unknown built-in tool: return `400`.
- Missing, disabled, or unusable MCP server: return `400`.
- Session not owned by the Agent: return `404`.
- Concurrent run for the same session: return `409`.
- Model/runtime failure: mark the session failed and emit `failed`.

Concurrency rule:

- A session can have only one active Agent run at a time.
- The frontend disables sending while a run is active.

## Frontend Agent form

Add a `能力` section between model selection and system prompt.

### Built-in tools

Render built-in tools as checkbox cards with:

- label
- technical name
- description
- enabled/unavailable state

Selected values are saved to `draft.tool_allowlist`.

If an existing draft references a tool that is no longer returned by capabilities, show it as an unavailable selected item and block save until the user removes or replaces it. This matches the existing model/provider unavailable-value behavior.

### MCP servers

Render MCP servers as checkbox cards with:

- name
- runtime status
- enabled state
- tool count

Selected values are saved to `draft.mcp_server_ids`.

The UI can display disabled or stopped servers, but backend validation is authoritative. Deleted servers referenced by an existing draft should be shown as unavailable and block save.

### Save behavior

After a successful create or edit save, navigate to:

```txt
/agents/:agentId/chat
```

Cancel still navigates back to `/agents`.

## Frontend chat page

Add route:

```txt
/agents/:agentId/chat
```

Page layout:

- Header with Agent name, model, built-in tool count, MCP server count, and a link back to edit.
- Transcript area backed by `useSessionStream(sessionId)`.
- Composer with a multiline input and send button.
- Empty state that invites the user to send the first message to test the current draft.

Composer behavior:

- `Enter` sends.
- `Shift+Enter` inserts a newline.
- Sending is disabled while a run is active.
- If a run is already active and the backend returns `409`, show a concise warning.

Message rendering:

- `user`: right-aligned bubble.
- `assistant`: left-aligned markdown using existing `StreamMarkdown`.
- `tool`: collapsible card with tool name and concise output.
- Live assistant deltas render as a temporary assistant bubble until the persisted assistant message arrives.
- Thinking deltas do not show content; only show a lightweight thinking state.

## Tests

Backend tests:

- Capabilities endpoint returns built-in tools and MCP summaries.
- Agent create/update persists `tool_allowlist` and `mcp_server_ids`.
- Agent session start creates a session, writes the user message, and starts a run.
- Disabled/incomplete Agent returns `400`.
- Concurrent run for the same session returns `409`.

Frontend tests:

- `AgentForm` renders built-in tool and MCP capability selections.
- `AgentForm` includes selected capabilities in create/update payloads.
- Create/edit save redirects to `/agents/:agentId/chat`.
- `AgentChatPage` sends first and follow-up messages.
- `AgentChatPage` subscribes to session stream and disables concurrent sends.

## Implementation order

1. Add backend capability registry and capabilities endpoint.
2. Add backend Agent session API and service orchestration.
3. Extend frontend Agent API/types/hooks for capabilities and sessions.
4. Extend `AgentForm` capability selection and save redirects.
5. Add `AgentChatPage` route and transcript/composer UI.
6. Add targeted backend and frontend tests.

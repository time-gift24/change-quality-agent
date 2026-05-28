# ReAct Agent Config Frontend Design

Date: 2026-05-28

## Context

The backend already exposes ReAct agent draft CRUD under `/api/agents`. It also
supports stored LLM providers under `/api/v1/llm-providers` and internal
CodeAgent models through the `codeagent:<model-name>` convention.

The frontend currently has admin management pages for MCP servers and LLM
providers, but no page for configuring ReAct agent drafts. This design adds the
smallest useful admin UI for creating and editing agent draft configuration.

## Goals

- Add an admin-only sidebar entry named `Agent 配置`.
- Add `/agents`, `/agents/new`, and `/agents/:agentId/edit` routes.
- Let admins create and edit the core agent draft fields:
  - `display_name`
  - `description`
  - `enabled`
  - `system_prompt`
  - model source and model
- Make `provider_id` selection a dropdown only.
- Offer a hard-coded CodeAgent model dropdown for internal models.
- Keep the implementation aligned with the existing `llmProviders` and `mcp`
  feature structure.

## Non-Goals

- No agent detail page.
- No publish action.
- No delete action.
- No test-run UI.
- No editing for `model_config`, `tool_allowlist`, or `mcp_server_ids`.
- No backend API changes unless implementation uncovers an API contract mismatch.

## Recommended Approach

Create a new `frontend/src/features/agents` feature. It should mirror the
current `llmProviders` frontend shape:

- `api.ts` wraps `/api/agents`.
- `types.ts` owns the TypeScript API shapes.
- `hooks.ts` owns list, detail, and mutation state.
- `components/AgentTable.tsx` renders the lightweight list.
- `components/AgentForm.tsx` renders the create/edit form.
- `pages/AgentListPage.tsx`, `pages/AgentFormPage.tsx`, and
  `pages/AgentPageLayout.tsx` own routing-level UI.

The app shell remains in `frontend/src/app/App.tsx`. Agent pages must not create
their own router, sidebar, or viewport frame.

## Routes And Navigation

Add a protected admin route group:

- `/agents`: lightweight agent list.
- `/agents/new`: create draft form.
- `/agents/:agentId/edit`: edit draft form.

Add `agents` to `WorkspaceRouteKey`, `workspaceRoutes`, and
`workspaceSidebarRoutes`. `getWorkspaceRouteKey()` should match `/agents`
before falling back to SOP. The sidebar item should be visible only to admins,
using the existing `requiresAdmin` route policy.

## List Page

The `/agents` page should stay intentionally small:

- Header title: `Agent 配置`.
- Primary CTA: `新增 Agent`.
- Search input and refresh button.
- Table columns:
  - Agent name
  - Enabled status
  - Model
  - Provider
  - Draft status
  - Updated time
  - Actions
- The only first-version action is `编辑`.

Provider display can be resolved client-side from the loaded provider list. If a
provider is missing or disabled, the list can display the raw `provider_id`.

## Form Behavior

Use one `AgentForm` for create and edit. The form has a `modelSource` state:

- `codeagent`: submit `provider_id: null` and a selected hard-coded
  `codeagent:<model-name>` model.
- `provider`: require an enabled provider from the provider dropdown, then
  require a model from that provider's `models` list.

Initial hard-coded CodeAgent model options:

- `codeagent:deepseek-v4-pro`
- `codeagent:codeagent-v4-pro`

Provider mode must not allow free-form `provider_id`. It must use a dropdown
populated from enabled LLM providers. When the selected provider has no models,
disable save and show a short message telling the admin to add models on the LLM
Provider page first.

## API Payloads

Create calls `POST /api/agents`:

```json
{
  "display_name": "Release Reviewer",
  "description": "Checks release risk.",
  "draft": {
    "system_prompt": "You are a careful reviewer.",
    "model": "codeagent:deepseek-v4-pro",
    "provider_id": null,
    "model_config": {},
    "tool_allowlist": [],
    "mcp_server_ids": []
  }
}
```

Edit calls `PATCH /api/agents/{agent_id}/draft` and sends:

```json
{
  "display_name": "Release Reviewer",
  "description": "Checks release risk.",
  "enabled": true,
  "draft": {
    "system_prompt": "You are a careful reviewer.",
    "model": "gpt-5-mini",
    "provider_id": "00000000-0000-0000-0000-000000000000",
    "model_config": {},
    "tool_allowlist": [],
    "mcp_server_ids": []
  }
}
```

The hidden draft fields always submit as an empty object or empty arrays in this
first version. This preserves the backend draft shape without exposing advanced
runtime controls.

## Validation And Errors

Client validation should cover:

- `display_name` is required.
- `system_prompt` is required.
- CodeAgent mode requires a CodeAgent model option.
- Provider mode requires an enabled provider.
- Provider mode requires a model from the selected provider's `models` list.

API failures should render an inline alert in the page body. Loading failures
for the agent or provider list should render the same compact alert style used
by existing admin pages. Save success returns to `/agents` with a transient
success notice.

## Testing

Add focused frontend tests:

- `agents/api.test.ts`: paths and payloads for list, get, create, and update
  draft.
- `AgentForm.test.tsx`: CodeAgent dropdown, provider dropdown, provider model
  dropdown, disabled save when provider has no models, and payload shape.
- `AgentPages.test.tsx`: list search, new/edit navigation, and save redirect.
- Existing sidebar/routing tests: admin sees `Agent 配置`; non-admin does not;
  `/agents` is protected.

Run at minimum:

- `npm test` in `frontend/`
- `npm run build` in `frontend/`

Because this is a frontend-only change, backend tests are optional during
implementation unless API contract changes are made.

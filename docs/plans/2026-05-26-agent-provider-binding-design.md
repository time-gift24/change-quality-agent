# Agent Provider Binding Design

Date: 2026-05-26

## Context

The backend now has CRUD APIs for user-scoped and admin-managed global LLM
provider credentials. Agent creation and runtime execution still use only the
agent draft `model` string. There is no link from an agent version to a stored
provider credential, so test runs cannot use the saved API key or base URL.

This change connects the two systems with the smallest useful binding: an agent
draft can reference one provider credential by ID, publishing snapshots that ID
onto the immutable agent version, and test-run execution resolves the credential
at runtime.

## Goals

- Let agent drafts bind to a provider credential with `provider_id`.
- Snapshot `provider_id` into `agent_versions` when an agent is published.
- Keep existing agents without `provider_id` working exactly as they do today.
- Let test runs use provider credentials when a published version has
  `provider_id`.
- Support compatibility auth for test runs: user headers are optional.
- Allow user provider credentials only when the run has the matching user ID.
- Allow global provider credentials with or without user headers.

## Non-Goals

- Do not add default provider selection.
- Do not bind providers by provider name or slug.
- Do not validate provider existence during create/update/publish.
- Do not implement real SSO.
- Do not implement KMS or secret manager integration.
- Do not migrate existing agents to provider-backed execution.

## Recommended Approach

Use a nullable `provider_id` on both the agent draft schema and published agent
version model.

`AgentDraftConfig.provider_id` is optional. `create_agent` and `update_draft`
persist it as part of the draft JSON without provider lookup. `publish_agent`
copies it into `AgentVersion.provider_id`. Runtime resolution is the only place
that checks whether the referenced provider exists and whether the current run
identity may use it.

This keeps the create/update API lightweight and avoids turning provider
selection into a blocking dependency for draft editing. The tradeoff is that a
bad provider ID can be saved and published; the user sees the failure when the
agent run executes.

## Data Model

Add a nullable column:

```text
agent_versions.provider_id UUID nullable
```

No foreign key is required in this version. A provider credential can be
soft-deleted or become unavailable after an agent version is published, and the
runtime should report that as a run failure rather than blocking historical
agent version records.

Draft config shape:

```json
{
  "system_prompt": "You are a release reviewer.",
  "model": "gpt-4.1-mini",
  "provider_id": "00000000-0000-0000-0000-000000000000",
  "model_config": {
    "temperature": 0
  },
  "tool_allowlist": [],
  "mcp_server_ids": []
}
```

`provider_id` may be omitted or null for legacy behavior.

## Runtime Resolution

When `AgentRuntime.run()` receives an agent version:

1. If `version.provider_id` is null, keep the current behavior:
   `init_chat_model(version.model, **version.model_config)`.
2. If `version.provider_id` is present, load an active `llm_provider`
   credential by ID.
3. If the run has a user ID, allow:
   - a user-scoped credential owned by that user
   - a global credential with `owner_user_id IS NULL`
4. If the run has no user ID, allow only a global credential.
5. Initialize the model with the agent version's `model` and `model_config`,
   plus provider credential fields:
   - API key from `api_key_ciphertext`
   - base URL from `base_url` when present
   - provider name from `provider` when needed by the model factory

The agent version's `model` wins over the provider record's `model`. The
provider record's `model` remains CRUD metadata or a future default, avoiding
surprising runtime changes when a provider is edited later.

## Test-Run Identity

`POST /api/agents/{agent_key}/test-runs` accepts fake auth headers but does not
require them:

```text
X-User-Id: user-123
X-User-Role: user | admin
```

The route stores optional identity context with the run payload/debug metadata.
The background executor reads that identity and passes it to provider
resolution.

Compatibility behavior:

- Existing clients without headers still receive `202` for valid agent test
  runs.
- Runs without a user ID can only use global providers.
- Runs with a user ID can use that user's provider or a global provider.

## Error Handling

- `create_agent` and `update_draft` reject malformed UUIDs through Pydantic.
- `create_agent`, `update_draft`, and `publish_agent` do not check provider
  existence or authorization.
- `start_test_run` still returns `202` unless the agent or version selector is
  invalid.
- Background execution marks the run failed when:
  - `provider_id` does not exist
  - the provider is inactive
  - the provider is not an `llm_provider`
  - the provider is user-scoped and the run has no user ID
  - the provider is user-scoped and owned by a different user

The failure should be recorded through the existing run error event path.

## Tests

Add focused tests for:

- `AgentDraftConfig` accepts optional `provider_id` and legacy drafts without it.
- The agent version model exposes nullable `provider_id`.
- The migration adds `agent_versions.provider_id`.
- Publishing copies draft `provider_id` into `AgentVersion.provider_id`.
- Test-run creation stores optional fake auth context.
- Runtime uses legacy model initialization when `provider_id` is absent.
- Runtime resolves global provider without user identity.
- Runtime resolves user provider only when identity matches.
- Runtime fails when provider is missing, inactive, or unauthorized.

## Open Tradeoff

This design intentionally defers create-time validation. That keeps the change
small and compatible, but users can save a bad provider reference and only
discover it during a test run. A future iteration can add validation to
`create_agent` and `update_draft` once the UI and product rules for provider
selection are settled.

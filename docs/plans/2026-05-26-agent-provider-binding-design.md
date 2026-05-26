# Agent Provider Binding Design

Date: 2026-05-26

## Context

The backend now has CRUD APIs for user-scoped and admin-managed global LLM
provider credentials. Agent creation and runtime execution still store model
selection directly on the agent draft and published agent version. That creates
two competing sources of truth now that provider credentials also contain the
provider's model, API key, and base URL.

This change makes provider credentials the only model source for agent
execution. An agent draft references one provider credential by ID, publishing
snapshots that ID onto the immutable agent version. Test-run execution resolves
the credential and uses its model, API key, and base URL.

## Goals

- Let agent drafts bind to a provider credential with required `provider_id`.
- Snapshot `provider_id` into `agent_versions` when an agent is published.
- Let test runs use provider credentials when a published version has
  `provider_id`.
- Support compatibility auth for test runs: user headers are optional.
- Allow user provider credentials only when the run has the matching user ID.
- Allow global provider credentials with or without user headers.
- Remove direct model storage from agent drafts and published agent versions.

## Non-Goals

- Do not add default provider selection.
- Do not bind providers by provider name or slug.
- Do not validate provider existence during create/update/publish.
- Do not implement real SSO.
- Do not implement KMS or secret manager integration.
- Do not keep a fallback path that runs agent versions without a provider.

## Recommended Approach

Use a required `provider_id` on the agent draft schema and a non-null
`provider_id` on published agent versions.

`AgentDraftConfig.model` is removed. `AgentVersion.model` is removed.
`create_agent` and `update_draft` persist `provider_id` as part of the draft JSON
without provider lookup. `publish_agent` copies it into
`AgentVersion.provider_id`. Runtime resolution is the only place that checks
whether the referenced provider exists and whether the current run identity may
use it.

This keeps the create/update API lightweight and avoids turning provider
selection into a blocking dependency for draft editing. The tradeoff is that a
bad provider ID can be saved and published; the user sees the failure when the
agent run executes.

## Data Model

Change published agent versions:

```text
agent_versions.provider_id UUID not null
agent_versions.model removed
```

No foreign key is required in this version. A provider credential can be
soft-deleted or become unavailable after an agent version is published, and the
runtime should report that as a run failure rather than blocking historical
agent version records.

Draft config shape:

```json
{
  "system_prompt": "You are a release reviewer.",
  "provider_id": "00000000-0000-0000-0000-000000000000",
  "model_config": {
    "temperature": 0
  },
  "tool_allowlist": [],
  "mcp_server_ids": []
}
```

`provider_id` is required. `model_config` remains on the draft/version because
runtime parameters such as temperature are agent behavior, not provider identity.

## Runtime Resolution

When `AgentRuntime.run()` receives an agent version:

1. Load an active `llm_provider` credential by `version.provider_id`.
2. If the run has a user ID, allow:
   - a user-scoped credential owned by that user
   - a global credential with `owner_user_id IS NULL`
3. If the run has no user ID, allow only a global credential.
4. Initialize the model with provider credential fields plus the agent version's
   `model_config`:
   - model from `provider_credentials.model`
   - API key from `api_key_ciphertext`
   - base URL from `base_url` when present
   - provider name from `provider` when needed by the model factory

The provider record's `model` is the only model source. Editing a provider's
model changes future runs for agent versions bound to that provider.

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
  - the provider has no `model`
  - the provider is user-scoped and the run has no user ID
  - the provider is user-scoped and owned by a different user

The failure should be recorded through the existing run error event path.

## Tests

Add focused tests for:

- `AgentDraftConfig` requires `provider_id` and no longer accepts `model`.
- The agent version model exposes non-null `provider_id` and no longer has
  `model`.
- The migration adds `agent_versions.provider_id` and drops
  `agent_versions.model`.
- Publishing copies draft `provider_id` into `AgentVersion.provider_id`.
- Test-run creation stores optional fake auth context.
- Runtime resolves global provider without user identity.
- Runtime resolves user provider only when identity matches.
- Runtime fails when provider is missing, inactive, or unauthorized.

## Open Tradeoff

This design intentionally defers create-time validation. That keeps the change
small, but users can save a bad provider reference and only discover it during a
test run. A future iteration can add validation to `create_agent` and
`update_draft` once the UI and product rules for provider selection are settled.

# LLM Provider CRUD Design

Date: 2026-05-27

## Summary

Add a first-class LLM provider resource for ordinary LangChain model providers while keeping `codeagent:<model>` as a special runtime path. Agents reference ordinary provider resources by `provider_key`; provider credentials and connection details stay out of agent drafts and published versions.

## Goals

- Manage ordinary LangChain provider resources through backend CRUD and frontend CRUD.
- Let agent drafts and versions reference a provider by stable `provider_key`.
- Keep provider secrets centralized, mutable, and masked in API responses.
- Preserve existing behavior for `codeagent:<model>` and legacy full LangChain model strings.
- Reuse current runtime error/event behavior for missing, disabled, or invalid providers.

## Backend Data Model

Add `llm_providers`:

- `id`
- `key`, unique stable reference, e.g. `openai-main`
- `display_name`
- `description`
- `provider_type`, passed to `init_chat_model` as `model_provider`, e.g. `openai`, `anthropic`, `google_genai`, `azure_openai`
- `base_url`
- `api_key`
- `default_headers`
- `default_query`
- `enabled`
- `created_at`, `updated_at`, `deleted_at`

Secrets are stored for runtime use but never returned in plaintext. API responses expose `api_key_configured: true | false`; sensitive header values are masked.

Add nullable `provider_key` to `agent_versions`. Agent drafts continue living in `agents.draft_config` JSONB and may include optional `provider_key`.

## Backend API

Add `/api/llm-providers`:

- `GET /api/llm-providers`
- `POST /api/llm-providers`
- `GET /api/llm-providers/{provider_key}`
- `PATCH /api/llm-providers/{provider_key}`
- `DELETE /api/llm-providers/{provider_key}`

PATCH semantics:

- Omitted `api_key` preserves the existing value.
- Explicit `api_key: null` clears it.
- Provided string replaces it.

Provider delete is soft delete. If a deleted or disabled provider is referenced at runtime, the run fails explicitly instead of falling back silently.

## Agent Runtime Rules

Model resolution has three paths:

1. `provider_key` is set: resolve current `llm_providers.key`, require `enabled`, and call:

   ```python
   init_chat_model(
       model=version.model,
       model_provider=provider.provider_type,
       api_key=provider.api_key,
       base_url=provider.base_url,
       default_headers=provider.default_headers,
       default_query=provider.default_query,
       **version.model_config,
   )
   ```

   `model` must be a bare model name. Prefixes such as `codeagent:*` or `openai:*` are rejected when `provider_key` is present.

2. `provider_key` is absent and `model` starts with `codeagent:`: use the existing CodeAgent runtime factory and token provider.

3. `provider_key` is absent and `model` is any other LangChain model string: keep the existing fallback `init_chat_model(model, **model_config)` for compatibility.

Published versions store only the `provider_key`, not provider credentials. Runtime always reads the provider's current configuration, so key or base URL rotation affects existing versions immediately.

## Frontend Design

Add a “模型 Provider” entry in the workspace sidebar, sibling to MCP 管理.

Routes:

- `/llm-providers`
- `/llm-providers/new`
- `/llm-providers/:providerKey`
- `/llm-providers/:providerKey/edit`

Pages follow the existing MCP CRUD pattern:

- List page: search, enabled filter, refresh, create button.
- Table columns: name, key, provider type, base URL, API key configured, enabled, updated time, actions.
- Detail page: provider summary, masked headers/query, credential status.
- Form page: create/edit provider.

Form fields:

- `key`, create-only
- `display_name`
- `description`
- `provider_type`, select with common values plus free input support
- `base_url`
- `api_key`, password input; blank on edit preserves existing value; explicit clear option clears it
- `default_headers`, KEY=VALUE multiline
- `default_query`, KEY=VALUE multiline
- `enabled`

No test-connection button in v1.

## Validation And Errors

- Duplicate provider key returns `409`.
- Missing provider returns `404` in provider APIs and runtime `LlmProviderNotFound` in run events.
- Disabled provider fails runtime with `LlmProviderDisabled`.
- `provider_key` with prefixed model fails draft validation/publish with `400`.
- API masks secret-like header keys containing authorization, token, secret, api-key, key, password, or credential.

## Tests

Backend:

- Provider schema masking and `api_key_configured` behavior.
- Provider CRUD repository and API, including duplicate key, soft delete, PATCH api_key preserve/clear/replace.
- Agent draft/version provider_key persistence.
- Runtime provider lookup, init_chat_model args, missing/disabled provider errors.
- Compatibility for `codeagent:*` and legacy no-provider model strings.
- OpenAPI contract updates.

Frontend:

- Provider API client request and error behavior.
- List page loading/error/empty/search/filter/create navigation.
- Form create/edit, api_key preserve, api_key clear, KEY=VALUE parsing.
- Detail page masked display.
- Sidebar route navigation and active state.

## Compatibility

Existing agents without `provider_key` continue to run. `codeagent:<model>` remains valid without a provider resource. Ordinary provider resources are additive and do not change MCP or SOP pages.

# LLM Provider CRUD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add CRUD management for ordinary LangChain `init_chat_model` providers, while keeping `codeagent:<model>` as the special internal model path. Agent drafts/versions can reference a stored provider via `provider_key`; provider secrets stay in backend storage and are never exposed to the frontend.

**Architecture:** Add a backend `llm_providers` resource with repository, schemas, API routes, OpenAPI contract, and DB migration. Extend agent draft/version persistence with optional `provider_key`. Update runtime model creation so `provider_key` resolves a provider and calls LangChain `init_chat_model`, while no `provider_key` keeps existing `codeagent:` and raw LangChain fallback behavior. Add a frontend LLM Providers section modeled after the MCP CRUD UI and aligned with `DESIGN.md`.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, LangChain `init_chat_model`, Vite, React 19, TypeScript, Tailwind CSS v4, Vitest.

---

## Current Baseline

- Worktree: `/Users/wanyaozhong/Projects/change-quality-agent/.worktrees/internal-chat-model-config`
- Branch: `codex/internal-chat-model-config`
- Existing special factory: `app/core/llm_models.py` supports `codeagent:<model>` and falls back to `init_chat_model`.
- Existing runtime: `app/core/agent_runtime.py` builds chat models from `version.model` and `version.model_config`.
- Existing CRUD pattern to follow: backend MCP files under `app/api/v1/mcp.py`, `app/schemas/mcp.py`, `app/repositories/mcp_servers.py`; frontend MCP files under `frontend/src/features/mcp/`.
- Design reference: `docs/plans/2026-05-27-llm-provider-crud-design.md`.

## Public Contract

- New provider resource key format: lowercase letters, digits, `_`, `-`, starting with a lowercase letter or digit.
- Agent draft/version accepts optional `provider_key`.
- If `provider_key` is set, `model` must be a bare provider model name such as `gpt-5-mini`, not `openai:gpt-5-mini` and not `codeagent:...`.
- If `provider_key` is absent and `model` starts with `codeagent:`, use the internal CodeAgent path.
- If `provider_key` is absent and `model` is any other value, keep existing `init_chat_model(model, **model_config)` fallback.
- Provider secrets are write-only through the API. Reads return `api_key_configured` and masked header/query values only.
- Editing a provider affects future runs of every Agent version that references its `provider_key`.
- Soft-deleted or disabled providers remain unavailable to runtime; runtime should raise a readable error instead of silently falling back.

## Task 1: Backend Provider Model, Migration, And Repository Tests

Write failing tests first.

Create or update:

- `tests/test_llm_provider_repository.py`
- `app/models/llm_providers.py`
- `app/models/__init__.py`
- `app/repositories/llm_providers.py`
- `migrations/versions/20260527_0004_create_llm_providers.py`

Test cases:

- Creating a provider persists `key`, `display_name`, `provider_type`, `base_url`, `api_key`, `default_headers`, `default_query`, and `enabled`.
- Duplicate active or soft-deleted keys are rejected.
- List excludes soft-deleted providers by default.
- Detail by key returns enabled and disabled providers if not deleted.
- Soft delete sets `deleted_at` and keeps the key reserved.
- Updating with omitted `api_key` preserves the old key; updating with `api_key=None` clears it; updating with a string replaces it.

Implementation details:

- Table name: `llm_providers`.
- Columns:
  - `id UUID primary key`
  - `key String unique not null index`
  - `display_name String not null`
  - `description Text nullable`
  - `provider_type String not null`
  - `base_url String nullable`
  - `api_key Text nullable`
  - `default_headers JSON not null default {}`
  - `default_query JSON not null default {}`
  - `enabled Boolean not null default true`
  - `created_at DateTime timezone not null`
  - `updated_at DateTime timezone not null`
  - `deleted_at DateTime timezone nullable index`
- Repository should expose simple async methods: `list`, `get_by_key`, `create`, `update`, `soft_delete`.
- Define repository errors with readable messages: `LlmProviderAlreadyExistsError`, `LlmProviderNotFoundError`.

Verification:

```bash
uv run pytest tests/test_llm_provider_repository.py -q
```

Expected result:

```text
passed
```

Commit:

```bash
git add app/models app/repositories tests/test_llm_provider_repository.py migrations/versions/20260527_0004_create_llm_providers.py
git commit -m "Add LLM provider repository"
```

## Task 2: Provider Schemas, Masking, And API Routes

Write failing tests first.

Create or update:

- `tests/test_llm_provider_schemas.py`
- `tests/test_llm_providers_api.py`
- `app/schemas/llm_providers.py`
- `app/api/v1/llm_providers.py`
- `app/main.py`

Test cases:

- `POST /api/v1/llm-providers` creates a provider and does not return plaintext `api_key`.
- `GET /api/v1/llm-providers` returns summaries with `api_key_configured`.
- `GET /api/v1/llm-providers/{provider_key}` returns detail with masked secret-like headers and query values.
- `PATCH /api/v1/llm-providers/{provider_key}` preserves `api_key` when omitted and clears it when explicitly null.
- `DELETE /api/v1/llm-providers/{provider_key}` soft deletes and subsequent GET returns 404.
- Duplicate create returns 409.
- Invalid key returns 422.

Implementation details:

- Schema names:
  - `LlmProviderCreate`
  - `LlmProviderUpdate`
  - `LlmProviderSummary`
  - `LlmProviderDetail`
- Request fields:
  - `key`, `display_name`, `description`, `provider_type`, `base_url`, `api_key`, `default_headers`, `default_query`, `enabled`
- Response fields:
  - all non-secret fields
  - `api_key_configured: bool`
  - masked `default_headers` and `default_query`
- Mask values whose key contains `key`, `token`, `secret`, `authorization`, `password`, or `credential`, case-insensitive.
- Do not add MCP admin-token authorization to these routes; match existing Agent CRUD accessibility.

Verification:

```bash
uv run pytest tests/test_llm_provider_schemas.py tests/test_llm_providers_api.py -q
```

Expected result:

```text
passed
```

Commit:

```bash
git add app/api/v1 app/schemas app/main.py tests/test_llm_provider_schemas.py tests/test_llm_providers_api.py
git commit -m "Add LLM provider API"
```

## Task 3: Agent Draft And Version `provider_key`

Write failing tests first.

Create or update:

- `tests/test_agent_schemas.py`
- `tests/test_agent_repository.py`
- `tests/test_agents_api.py`
- `app/schemas/agents.py`
- `app/models/agents.py`
- `app/repositories/agents.py`
- `app/services/agents.py`
- `migrations/versions/20260527_0005_add_agent_provider_key.py`

Test cases:

- Draft create/update accepts `provider_key`.
- Draft validation rejects `provider_key` with `model` containing `:`.
- Draft validation allows `model="codeagent:..."` only when `provider_key` is absent.
- Publishing copies draft `provider_key` onto the created version.
- Version summary/detail includes `provider_key`.
- Existing payloads without `provider_key` remain valid.

Implementation details:

- Add nullable `provider_key` to draft config schema and persisted version model.
- Keep the draft JSON shape backward-compatible.
- Use schema-level validation for the `provider_key` and `model` rule.
- Do not validate provider existence during draft save; runtime and publish flows can operate independently from provider lifecycle.

Verification:

```bash
uv run pytest tests/test_agent_schemas.py tests/test_agent_repository.py tests/test_agents_api.py -q
```

Expected result:

```text
passed
```

Commit:

```bash
git add app/schemas/agents.py app/models/agents.py app/repositories/agents.py app/services/agents.py tests/test_agent_schemas.py tests/test_agent_repository.py tests/test_agents_api.py migrations/versions/20260527_0005_add_agent_provider_key.py
git commit -m "Allow agents to reference LLM providers"
```

## Task 4: Runtime Provider Resolution

Write failing tests first.

Create or update:

- `tests/test_llm_models.py`
- `tests/test_agent_runtime.py`
- `tests/test_agent_test_run_executor.py`
- `app/core/llm_models.py`
- `app/core/agent_runtime.py`
- `app/services/agent_test_runs.py`

Test cases:

- `create_provider_chat_model("gpt-5-mini", provider, temperature=0)` calls `init_chat_model` with:
  - `model="gpt-5-mini"`
  - `model_provider=provider.provider_type`
  - `api_key=provider.api_key`
  - `base_url=provider.base_url`
  - `default_headers=provider.default_headers`
  - `default_query=provider.default_query`
  - original `model_config`
- Provider config omits `api_key`, `base_url`, `default_headers`, or `default_query` when empty.
- Runtime with `provider_key` uses provider resolver and does not call the default `model_factory`.
- Runtime without `provider_key` keeps current `codeagent:` and raw `init_chat_model` fallback behavior.
- Missing resolver for a `provider_key` raises a readable error.
- Missing, deleted, or disabled provider raises a readable runtime error.
- Agent test run executor wires a DB-backed provider resolver into `AgentRuntime`.

Implementation details:

- Keep `create_chat_model(model: str, **model_config)` as the default factory for non-provider paths.
- Add a focused function in `app/core/llm_models.py`, for example:

```python
def create_provider_chat_model(model: str, provider: LlmProviderRuntimeConfig, **model_config: Any) -> BaseChatModel:
    ...
```

- Avoid importing SQLAlchemy models directly into low-level factory code if practical. Use a small runtime dataclass/protocol such as `LlmProviderRuntimeConfig`.
- Add an `LlmProviderResolver` protocol to `app/core/agent_runtime.py` or a small core module:

```python
class LlmProviderResolver(Protocol):
    async def resolve(self, provider_key: str) -> LlmProviderRuntimeConfig: ...
```

- The DB-backed resolver can live near service wiring and use `LlmProviderRepository`.
- `_build_agent()` remains responsible only for reading `version.model`, `version.model_config`, and optional `version.provider_key`, then delegating model construction.
- Do not put token/header details into Agent draft/version fields.

Verification:

```bash
uv run pytest tests/test_llm_models.py tests/test_agent_runtime.py tests/test_agent_test_run_executor.py -q
```

Expected result:

```text
passed
```

Commit:

```bash
git add app/core app/services tests/test_llm_models.py tests/test_agent_runtime.py tests/test_agent_test_run_executor.py
git commit -m "Resolve stored LLM providers at runtime"
```

## Task 5: OpenAPI Contract And Backend Docs

Write failing tests first if the OpenAPI contract test needs updates.

Create or update:

- `api/openapi.yml`
- `docs/agent-crud-feature.md`
- `tests/test_openapi_contract.py`

Contract changes:

- Add `/api/v1/llm-providers` collection operations.
- Add `/api/v1/llm-providers/{provider_key}` detail operations.
- Add provider schemas matching backend Pydantic schemas.
- Add `provider_key` to Agent draft/version schemas.
- Document that `provider_key` and `codeagent:` are mutually exclusive.

Verification:

```bash
uv run pytest tests/test_openapi_contract.py -q
```

Expected result:

```text
passed
```

Commit:

```bash
git add api/openapi.yml docs/agent-crud-feature.md tests/test_openapi_contract.py
git commit -m "Document LLM provider contract"
```

## Task 6: Frontend LLM Providers CRUD

Read `DESIGN.md` and `frontend/DESIGN.md` before editing UI files.

Write failing tests first.

Create or update:

- `frontend/src/features/llmProviders/types.ts`
- `frontend/src/features/llmProviders/api.ts`
- `frontend/src/features/llmProviders/components/LlmProviderTable.tsx`
- `frontend/src/features/llmProviders/components/LlmProviderForm.tsx`
- `frontend/src/features/llmProviders/pages/LlmProviderListPage.tsx`
- `frontend/src/features/llmProviders/pages/LlmProviderFormPage.tsx`
- `frontend/src/features/llmProviders/pages/LlmProviderDetailPage.tsx`
- `frontend/src/features/llmProviders/__tests__/LlmProviderForm.test.tsx`
- `frontend/src/features/llmProviders/__tests__/LlmProviderPages.test.tsx`
- `frontend/src/app/App.tsx`
- `frontend/src/app/WorkspaceSidebar.tsx`
- `frontend/README.md`

UI behavior:

- Sidebar adds `LLM Providers`.
- Routes:
  - `/llm-providers`
  - `/llm-providers/new`
  - `/llm-providers/:providerKey`
  - `/llm-providers/:providerKey/edit`
- List shows provider key, display name, provider type, base URL, enabled state, and `api_key_configured`.
- Detail shows masked headers/query from API and never renders plaintext `api_key`.
- Form supports create/edit with fields:
  - key
  - display name
  - description
  - provider type
  - base URL
  - API key
  - default headers as simple `KEY=VALUE` lines
  - default query as simple `KEY=VALUE` lines
  - enabled
- Edit form leaves API key blank with helper text explaining blank means preserve; explicit clear should be available through a clear action or checkbox.
- Use existing MCP UI layout and design tokens; do not introduce a new visual system.

Verification:

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected result:

```text
Test Files ... passed
✓ built
```

Commit:

```bash
git add frontend/src frontend/README.md
git commit -m "Add LLM provider frontend"
```

## Task 7: Full Regression And Final Review

Run targeted backend regression:

```bash
uv run pytest tests/test_agent_runtime.py tests/test_agent_schemas.py tests/test_llm_models.py tests/test_llm_tokens.py tests/test_llm_provider_schemas.py tests/test_llm_provider_repository.py tests/test_llm_providers_api.py tests/test_openapi_contract.py -q
```

Run full backend suite:

```bash
uv run pytest -q
```

Run frontend suite:

```bash
cd frontend && npm test
cd frontend && npm run build
```

Check migration chain:

```bash
uv run pytest tests/test_migrations.py -q
```

Check git state:

```bash
git status --short --branch
```

Expected result:

```text
## codex/internal-chat-model-config
```

If all verification passes, commit any final fixes:

```bash
git add .
git commit -m "Implement LLM provider CRUD"
```

## Risk Notes

- Provider edits affect historical Agent versions immediately. This is intended, but API copy should make the blast radius explicit.
- Storing provider API keys in plaintext DB is acceptable for this implementation only because no secret manager requirement exists yet. Keep the write-only API boundary so storage can be replaced later.
- Do not silently downgrade to raw `init_chat_model` when `provider_key` resolution fails; that would run the wrong model/provider.
- Do not let `provider_key` carry CodeAgent auth. CodeAgent token refresh remains isolated behind the existing internal provider boundary.
- Avoid over-abstracting provider forms until there is a second UI needing the same `KEY=VALUE` editor.

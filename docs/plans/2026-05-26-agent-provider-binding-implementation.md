# Agent Provider Binding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make ReAct agent versions bind to LLM provider credentials, with provider credentials as the only source for runtime model selection.

**Architecture:** Remove direct `model` storage from agent drafts and published `agent_versions`. Add required `provider_id` to agent drafts and published versions. Runtime resolves the provider credential and initializes LangChain from provider `model`, `api_key_ciphertext`, `base_url`, and agent-owned `model_config`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL JSONB, LangChain 1.x, pytest, httpx.

Use @fastapi and @project-structure. Work only in `.worktrees/llm-provider-crud-design`. Do not stage unrelated `README.md` changes.

---

### Task 1: Replace Agent Draft `model` With Required `provider_id`

**Files:**
- Modify: `app/schemas/agents.py`
- Modify: `api/openapi.yml`
- Test: `tests/test_agent_schemas.py`
- Test: `tests/test_openapi_contract.py`
- Test: `tests/test_agents_api.py`

**Step 1: Write failing schema tests**

Add to `tests/test_agent_schemas.py`:

```python
from uuid import uuid4

from pydantic import ValidationError


def test_agent_draft_config_requires_provider_id() -> None:
    provider_id = uuid4()

    draft = AgentDraftConfig(
        system_prompt="Review changes.",
        provider_id=provider_id,
        model_config={"temperature": 0},
    )

    assert draft.provider_id == provider_id
    assert draft.model_dump(mode="json")["provider_id"] == str(provider_id)


def test_agent_draft_config_rejects_missing_provider_id() -> None:
    with pytest.raises(ValidationError):
        AgentDraftConfig(system_prompt="Review changes.")


def test_agent_draft_config_rejects_model_field() -> None:
    with pytest.raises(ValidationError):
        AgentDraftConfig(
            system_prompt="Review changes.",
            model="gpt-4.1-mini",
            provider_id=uuid4(),
        )
```

If `ValidationError` is already imported, reuse the existing import.

Add to `tests/test_openapi_contract.py`:

```python
def test_agent_draft_schema_uses_provider_id_instead_of_model() -> None:
    schema = load_contract()["components"]["schemas"]["AgentDraftConfig"]

    assert "provider_id" in schema["required"]
    assert "model" not in schema["properties"]
    assert schema["properties"]["provider_id"] == {
        "type": "string",
        "format": "uuid",
    }
```

Update existing API test helpers in `tests/test_agents_api.py` so `draft_payload()` uses `provider_id` and no longer includes `model`.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_schemas.py tests/test_openapi_contract.py tests/test_agents_api.py -q
```

Expected: FAIL because schemas and fixtures still use `model`.

**Step 3: Implement schema**

In `app/schemas/agents.py`:

```python
from uuid import UUID
```

Update `AgentDraftConfig`:

```python
class AgentDraftConfig(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    system_prompt: str = Field(min_length=1)
    provider_id: UUID
    model_parameters: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("model_config", "model_parameters"),
        serialization_alias="model_config",
    )
    tool_allowlist: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
```

**Step 4: Update OpenAPI contract**

In `api/openapi.yml`, update `AgentDraftConfig`:

```yaml
    AgentDraftConfig:
      type: object
      required:
      - system_prompt
      - provider_id
      properties:
        system_prompt:
          type: string
          minLength: 1
        provider_id:
          type: string
          format: uuid
        model_config:
          type: object
          additionalProperties: true
          default: {}
        tool_allowlist:
          type: array
          items:
            type: string
          default: []
        mcp_server_ids:
          type: array
          items:
            type: string
          default: []
```

Remove `model` from this schema and from examples in agent create/update docs.

**Step 5: Run tests**

Run:

```bash
uv run python -m pytest tests/test_agent_schemas.py tests/test_openapi_contract.py tests/test_agents_api.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/schemas/agents.py api/openapi.yml tests/test_agent_schemas.py tests/test_openapi_contract.py tests/test_agents_api.py
git commit -m "feat: bind agent drafts to providers"
```

### Task 2: Replace `agent_versions.model` With `provider_id`

**Files:**
- Modify: `app/models/agents.py`
- Create: `migrations/versions/20260526_0005_replace_agent_version_model.py`
- Modify: `tests/test_agent_models.py`
- Modify: `tests/test_migrations.py`

**Step 1: Write failing model and migration tests**

Add to `tests/test_agent_models.py`:

```python
def test_agent_version_model_uses_provider_id_instead_of_model() -> None:
    columns = AgentVersion.__table__.columns

    assert "provider_id" in columns
    assert columns["provider_id"].nullable is False
    assert "model" not in columns
```

Add to `tests/test_migrations.py`:

```python
def test_agent_provider_binding_migration_replaces_model() -> None:
    path = MIGRATIONS_DIR / "20260526_0005_replace_agent_version_model.py"

    assert path.exists()
    migration = path.read_text(encoding="utf-8")
    assert 'revision: str = "20260526_0005"' in migration
    assert 'down_revision: str | Sequence[str] | None = "20260526_0004"' in migration
    assert 'op.add_column("agent_versions"' in migration
    assert '"provider_id"' in migration
    assert 'op.drop_column("agent_versions", "model")' in migration
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_models.py::test_agent_version_model_uses_provider_id_instead_of_model tests/test_migrations.py::test_agent_provider_binding_migration_replaces_model -q
```

Expected: FAIL because the model and migration still use `model`.

**Step 3: Implement model**

In `app/models/agents.py`, remove:

```python
model: Mapped[str] = mapped_column(Text, nullable=False)
```

Add:

```python
provider_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
```

Keep `model_config`; runtime parameters remain agent-version data.

**Step 4: Implement migration**

Create `migrations/versions/20260526_0005_replace_agent_version_model.py`:

```python
"""replace agent version model with provider binding

Revision ID: 20260526_0005
Revises: 20260526_0004
Create Date: 2026-05-26

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260526_0005"
down_revision: str | Sequence[str] | None = "20260526_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_versions",
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.drop_column("agent_versions", "model")


def downgrade() -> None:
    op.add_column(
        "agent_versions",
        sa.Column("model", sa.Text(), nullable=False),
    )
    op.drop_column("agent_versions", "provider_id")
```

Note: this migration assumes no production rows need backfill yet. If a shared
database already has agent_versions rows, coordinate a backfill before applying.

**Step 5: Run tests and Alembic heads**

Run:

```bash
uv run python -m pytest tests/test_agent_models.py tests/test_migrations.py -q
uv run alembic heads
```

Expected: PASS, and Alembic reports `20260526_0005 (head)`.

**Step 6: Commit**

```bash
git add app/models/agents.py migrations/versions/20260526_0005_replace_agent_version_model.py tests/test_agent_models.py tests/test_migrations.py
git commit -m "feat: replace agent version model with provider binding"
```

### Task 3: Publish And Snapshot Provider Binding

**Files:**
- Modify: `app/repositories/agents.py`
- Modify: `app/repositories/runs.py`
- Modify: `app/schemas/agents.py`
- Test: `tests/test_agent_repository.py`
- Test: `tests/test_agent_test_runs.py`
- Test: `tests/test_agents_api.py`

**Step 1: Write failing publish test**

Add to `tests/test_agent_repository.py`:

```python
@repository_db_test
async def test_publish_agent_copies_provider_id_from_draft(session) -> None:
    provider_id = uuid4()
    repository = AgentRepository(session)
    await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        draft=AgentDraftConfig(
            system_prompt="Review releases.",
            provider_id=provider_id,
        ),
    )

    version = await repository.publish_agent("release-reviewer")

    assert version.provider_id == provider_id
```

**Step 2: Write failing response and run snapshot tests**

Update tests that previously asserted `model` on version summaries/details to assert `provider_id`.

Add or update in `tests/test_agent_test_runs.py`:

```python
async def test_create_agent_test_run_snapshots_provider_id() -> None:
    provider_id = uuid4()
    repository = FakeRunRepository()
    version = FakeAgentVersion(provider_id=provider_id)

    run = await repository.create_agent_test_run(
        agent_key="release-reviewer",
        agent_version=version,
        messages=[{"role": "user", "content": "Can this deploy?"}],
        input_preview="Can this deploy?",
    )

    assert run.subject_snapshot["agent_version"]["provider_id"] == str(provider_id)
    assert "model" not in run.subject_snapshot["agent_version"]
```

**Step 3: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_repository.py tests/test_agent_test_runs.py tests/test_agents_api.py -q
```

Expected: FAIL because publish and response code still reference `model`.

**Step 4: Implement publish copy**

In `app/repositories/agents.py`, update `publish_agent`:

```python
version = AgentVersion(
    agent_id=agent.id,
    version_number=await self._next_version_number(agent.id),
    system_prompt=draft.system_prompt,
    provider_id=draft.provider_id,
    model_config=dict(draft.model_parameters),
    tool_allowlist=list(draft.tool_allowlist),
    mcp_server_ids=list(draft.mcp_server_ids),
    published_by=published_by,
)
```

**Step 5: Update response schemas**

In `app/schemas/agents.py`, replace `model: str` with `provider_id: UUID` on
`AgentVersionSummary`. `AgentVersionDetail` inherits it.

**Step 6: Update run snapshot**

In `app/repositories/runs.py`, update `_agent_version_snapshot`:

```python
snapshot: dict[str, Any] = {
    "id": str(agent_version.id),
    "version_number": agent_version.version_number,
    "provider_id": str(agent_version.provider_id),
}
```

**Step 7: Run tests**

Run:

```bash
uv run python -m pytest tests/test_agent_repository.py tests/test_agent_test_runs.py tests/test_agents_api.py -q
```

Expected: PASS, with DB tests skipped unless `TEST_DATABASE_URL` is set.

**Step 8: Commit**

```bash
git add app/repositories/agents.py app/repositories/runs.py app/schemas/agents.py tests/test_agent_repository.py tests/test_agent_test_runs.py tests/test_agents_api.py
git commit -m "feat: publish agent provider binding"
```

### Task 4: Store Optional Test-Run User Context

**Files:**
- Modify: `app/api/v1/agents.py`
- Modify: `app/services/agents.py`
- Modify: `app/repositories/runs.py`
- Test: `tests/test_agent_test_runs.py`
- Test: `tests/test_agents_api.py`

**Step 1: Write failing service test**

Add to `tests/test_agent_test_runs.py`:

```python
async def test_start_test_run_persists_optional_user_context() -> None:
    repository = FakeAgentRepository()
    run_repository = FakeRunRepository()
    service = AgentService(
        repository=repository,
        run_repository=run_repository,
        schedule_test_run=lambda run_id: None,
        commit=lambda: None,
    )

    await service.start_test_run(
        "release-reviewer",
        AgentTestRunCreate(messages=[{"role": "user", "content": "Can this deploy?"}]),
        current_user=CurrentUser(user_id="user-123", role="user"),
    )

    assert run_repository.created_kwargs["current_user"] == {
        "user_id": "user-123",
        "role": "user",
    }
```

Import `CurrentUser` from `app.api.auth`.

**Step 2: Write failing API test**

Add to `tests/test_agents_api.py`:

```python
async def test_start_agent_test_run_accepts_optional_user_context() -> None:
    repository = FakeAgentRepository()
    run_repository = FakeRunRepository()
    override_dependencies(repository=repository, run_repository=run_repository)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/agents/release-reviewer/test-runs",
            headers={"x-user-id": "user-123"},
            json={"messages": [{"role": "user", "content": "Can this deploy?"}]},
        )

    assert response.status_code == 202
    assert run_repository.created_kwargs["current_user"] == {
        "user_id": "user-123",
        "role": "user",
    }
```

Keep the existing no-header test unchanged to prove compatibility.

**Step 3: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_test_runs.py tests/test_agents_api.py -q
```

Expected: FAIL because `start_test_run` does not accept or persist user context.

**Step 4: Update service and route**

In `app/services/agents.py`, import `CurrentUser` and update `AgentService.start_test_run`:

```python
async def start_test_run(
    self,
    agent_key: str,
    request: AgentTestRunCreate,
    current_user: CurrentUser | None = None,
) -> AgentRunStartResult:
```

Pass:

```python
current_user_payload = (
    {"user_id": current_user.user_id, "role": current_user.role}
    if current_user is not None
    else None
)
```

to `RunRepository.create_agent_test_run(current_user=current_user_payload)`.

In `app/api/v1/agents.py`, read optional auth from middleware:

```python
current_user = getattr(request.state, "current_user", None)
result = await service.start_test_run(agent_key, payload, current_user=current_user)
```

Do not use `CurrentUserDep`; test-run auth remains optional.

**Step 5: Update run repository**

In `RunRepository.create_agent_test_run`, add:

```python
current_user: dict[str, str] | None = None,
```

Store it in `metadata_` and `subject_snapshot` only when present.

**Step 6: Run tests**

Run:

```bash
uv run python -m pytest tests/test_agent_test_runs.py tests/test_agents_api.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add app/api/v1/agents.py app/services/agents.py app/repositories/runs.py tests/test_agent_test_runs.py tests/test_agents_api.py
git commit -m "feat: persist agent test run user context"
```

### Task 5: Resolve Provider Credentials For Runtime

**Files:**
- Modify: `agent/react_runtime.py`
- Modify: `app/services/agents.py`
- Modify: `app/repositories/provider_credentials.py`
- Test: `tests/test_agent_runtime.py`
- Test: `tests/test_agent_test_run_executor.py`
- Test: `tests/test_provider_credential_repository.py`

**Step 1: Write failing runtime tests**

Add to `tests/test_agent_runtime.py`:

```python
class FakeProvider:
    def __init__(
        self,
        *,
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key_ciphertext="sk-test123456",
        model="gpt-4.1-mini",
    ):
        self.provider = provider
        self.base_url = base_url
        self.api_key_ciphertext = api_key_ciphertext
        self.model = model


class FakeProviderResolver:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    async def resolve(self, provider_id, user_id):
        self.calls.append((provider_id, user_id))
        return self.provider


async def test_runtime_resolves_provider_and_uses_provider_model() -> None:
    provider_id = uuid4()
    resolver = FakeProviderResolver(FakeProvider(model="gpt-4.1-mini"))
    factory = FakeModelFactory()
    runtime = AgentRuntime(model_factory=factory, provider_resolver=resolver)
    version = FakeVersion(provider_id=provider_id, model_config={"temperature": 0})

    await runtime.run(
        version=version,
        messages=[{"role": "user", "content": "Hi"}],
        current_user={"user_id": "user-123", "role": "user"},
    )

    assert resolver.calls == [(provider_id, "user-123")]
    assert factory.calls[0]["model"] == "gpt-4.1-mini"
    assert factory.calls[0]["kwargs"]["api_key"] == "sk-test123456"
    assert factory.calls[0]["kwargs"]["base_url"] == "https://api.openai.com/v1"
    assert factory.calls[0]["kwargs"]["temperature"] == 0
```

Remove or update legacy tests that expected runtime to run without a provider.

**Step 2: Write failing repository tests**

Add to `tests/test_provider_credential_repository.py`:

```python
@repository_db_test
async def test_get_runtime_llm_provider_allows_matching_user_provider(session) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal")
    )

    resolved = await repository.get_runtime_llm_provider(provider.id, "user-1")

    assert resolved is provider


@repository_db_test
async def test_get_runtime_llm_provider_rejects_user_provider_without_user(session) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal")
    )

    assert await repository.get_runtime_llm_provider(provider.id, None) is None


@repository_db_test
async def test_get_runtime_llm_provider_allows_global_without_user(session) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(**global_provider_values("global"))

    resolved = await repository.get_runtime_llm_provider(provider.id, None)

    assert resolved is provider
```

**Step 3: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_runtime.py tests/test_provider_credential_repository.py -q
```

Expected: FAIL because runtime and repository resolution are not implemented.

**Step 4: Add repository resolution method**

In `app/repositories/provider_credentials.py`, add `get_runtime_llm_provider`:

```python
async def get_runtime_llm_provider(
    self,
    provider_id: UUID,
    owner_user_id: str | None,
) -> ProviderCredential | None:
    conditions = [
        (ProviderCredential.scope == "global")
        & ProviderCredential.owner_user_id.is_(None)
    ]
    if owner_user_id is not None:
        conditions.append(
            (ProviderCredential.scope == "user")
            & (ProviderCredential.owner_user_id == owner_user_id)
        )
    statement = (
        self._active_llm_provider_statement()
        .where(ProviderCredential.id == provider_id)
        .where(or_(*conditions))
        .limit(1)
    )
    return await self._session.scalar(statement)
```

Import `or_` from SQLAlchemy.

**Step 5: Update runtime**

In `agent/react_runtime.py`, add a resolver dependency and remove reliance on
`version.model`:

```python
class RuntimeProviderUnavailableError(RuntimeError):
    pass


class NullProviderResolver:
    async def resolve(self, provider_id, user_id):
        raise RuntimeProviderUnavailableError(
            f"LLM provider is not available: {provider_id}"
        )
```

Update `AgentRuntime.__init__` with `provider_resolver=None`.

Update `run`:

```python
provider_id = getattr(version, "provider_id")
user_id = current_user.get("user_id") if current_user else None
provider = await self._provider_resolver.resolve(provider_id, user_id)
model_kwargs = dict(getattr(version, "model_config", {}) or {})
model_kwargs.update(_provider_model_kwargs(provider))
model = self._model_factory(provider.model, **model_kwargs)
```

Add:

```python
def _provider_model_kwargs(provider: Any) -> dict[str, Any]:
    if not provider.model:
        raise RuntimeProviderUnavailableError("LLM provider model is required.")
    kwargs = {"api_key": provider.api_key_ciphertext}
    if provider.base_url:
        kwargs["base_url"] = provider.base_url
    if provider.provider:
        kwargs["model_provider"] = provider.provider
    return kwargs
```

**Step 6: Wire resolver into executor**

In `app/services/agents.py`, import `ProviderCredentialRepository`.

Add:

```python
class ProviderCredentialRuntimeResolver:
    def __init__(self, repository: ProviderCredentialRepository) -> None:
        self._repository = repository

    async def resolve(self, provider_id: UUID, user_id: str | None):
        provider = await self._repository.get_runtime_llm_provider(provider_id, user_id)
        if provider is None:
            raise RuntimeError(f"LLM provider is not available: {provider_id}")
        return provider
```

Update `run_agent_test` with optional `provider_repository`. Create the default
runtime with `AgentRuntime(provider_resolver=ProviderCredentialRuntimeResolver(provider_repository))`.

Pass current user from run snapshot:

```python
result = await runtime.run(
    version=version,
    messages=list(run.subject_snapshot.get("messages", [])),
    current_user=run.subject_snapshot.get("current_user"),
)
```

Update `run_agent_test_with_new_session` to create and pass `ProviderCredentialRepository(session)`.

**Step 7: Run tests**

Run:

```bash
uv run python -m pytest tests/test_agent_runtime.py tests/test_agent_test_run_executor.py tests/test_provider_credential_repository.py -q
```

Expected: PASS, with DB tests skipped unless `TEST_DATABASE_URL` is set.

**Step 8: Commit**

```bash
git add agent/react_runtime.py app/services/agents.py app/repositories/provider_credentials.py tests/test_agent_runtime.py tests/test_agent_test_run_executor.py tests/test_provider_credential_repository.py
git commit -m "feat: resolve agent provider credentials at runtime"
```

### Task 6: Final Verification

**Files:**
- Modify: `api/openapi.yml` only if contract tests require more updates.
- Do not stage unrelated `README.md` unless the user explicitly asks.

**Step 1: Run focused tests**

Run:

```bash
uv run python -m pytest \
  tests/test_agent_schemas.py \
  tests/test_agent_models.py \
  tests/test_agent_repository.py \
  tests/test_agent_test_runs.py \
  tests/test_agent_test_run_executor.py \
  tests/test_agent_runtime.py \
  tests/test_provider_credential_repository.py \
  tests/test_agents_api.py \
  tests/test_openapi_contract.py \
  tests/test_migrations.py \
  -q
```

Expected: PASS, with DB tests skipped unless `TEST_DATABASE_URL` is set.

**Step 2: Run full tests**

Run:

```bash
uv run python -m pytest -q
```

Expected: PASS.

**Step 3: Verify Alembic graph**

Run:

```bash
uv run alembic heads
```

Expected:

```text
20260526_0005 (head)
```

**Step 4: Check status**

Run:

```bash
git status --short
```

Expected: only intentional files changed. `README.md` may still be an unrelated
unstaged local change from before this plan.

**Step 5: Commit final adjustments if needed**

If Task 6 changed files:

```bash
git add api/openapi.yml tests/test_openapi_contract.py
git commit -m "test: cover agent provider binding contract"
```

If no files changed, skip this commit.

# Agent Provider Binding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bind published ReAct agent versions to optional LLM provider credentials and use those credentials during agent test-run execution.

**Architecture:** Add nullable `provider_id` to agent draft schemas and published `agent_versions`. Create a small runtime provider resolver that uses the existing `provider_credentials` repository and optional test-run user context. Preserve legacy behavior when `provider_id` is absent.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL JSONB, LangChain 1.x, pytest, httpx.

Use @fastapi and @project-structure. Work only in `.worktrees/llm-provider-crud-design`. Do not stage unrelated `README.md` changes.

---

### Task 1: Add `provider_id` To Agent Schemas

**Files:**
- Modify: `app/schemas/agents.py`
- Test: `tests/test_agent_schemas.py`
- Test: `tests/test_openapi_contract.py`

**Step 1: Write failing schema tests**

Add to `tests/test_agent_schemas.py`:

```python
from uuid import UUID, uuid4


def test_agent_draft_config_accepts_optional_provider_id() -> None:
    provider_id = uuid4()

    draft = AgentDraftConfig(
        system_prompt="Review changes.",
        model="gpt-4.1-mini",
        provider_id=provider_id,
        model_config={"temperature": 0},
    )

    assert draft.provider_id == provider_id
    assert draft.model_dump(mode="json")["provider_id"] == str(provider_id)


def test_agent_draft_config_keeps_legacy_provider_id_optional() -> None:
    draft = AgentDraftConfig(
        system_prompt="Review changes.",
        model="gpt-4.1-mini",
    )

    assert draft.provider_id is None
    assert draft.model_dump(mode="json")["provider_id"] is None
```

Add to `tests/test_openapi_contract.py`:

```python
def test_agent_draft_schema_documents_provider_id() -> None:
    properties = load_contract()["components"]["schemas"]["AgentDraftConfig"][
        "properties"
    ]

    assert properties["provider_id"] == {
        "type": "string",
        "format": "uuid",
        "nullable": True,
    }
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_schemas.py::test_agent_draft_config_accepts_optional_provider_id tests/test_agent_schemas.py::test_agent_draft_config_keeps_legacy_provider_id_optional tests/test_openapi_contract.py::test_agent_draft_schema_documents_provider_id -q
```

Expected: FAIL because `provider_id` is not in `AgentDraftConfig` or the OpenAPI contract.

**Step 3: Implement schema and contract**

In `app/schemas/agents.py`, add:

```python
from uuid import UUID
```

and in `AgentDraftConfig`:

```python
provider_id: UUID | None = None
```

In `api/openapi.yml`, add `provider_id` to `AgentDraftConfig.properties`:

```yaml
        provider_id:
          type: string
          format: uuid
          nullable: true
```

Do not add `provider_id` to required fields.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/test_agent_schemas.py tests/test_openapi_contract.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/schemas/agents.py api/openapi.yml tests/test_agent_schemas.py tests/test_openapi_contract.py
git commit -m "feat: add provider binding to agent draft schema"
```

### Task 2: Add `provider_id` To Published Agent Versions

**Files:**
- Modify: `app/models/agents.py`
- Modify: `app/models/__init__.py` if needed
- Create: `migrations/versions/20260526_0005_add_agent_provider_binding.py`
- Modify: `tests/test_agent_models.py`
- Modify: `tests/test_migrations.py`

**Step 1: Write failing model and migration tests**

Add to `tests/test_agent_models.py`:

```python
def test_agent_version_model_has_optional_provider_id() -> None:
    columns = AgentVersion.__table__.columns

    assert "provider_id" in columns
    assert columns["provider_id"].nullable is True
```

Add to `tests/test_migrations.py`:

```python
def test_agent_provider_binding_migration_exists() -> None:
    path = MIGRATIONS_DIR / "20260526_0005_add_agent_provider_binding.py"

    assert path.exists()
    migration = path.read_text(encoding="utf-8")
    assert 'revision: str = "20260526_0005"' in migration
    assert 'down_revision: str | Sequence[str] | None = "20260526_0004"' in migration
    assert 'op.add_column("agent_versions"' in migration
    assert '"provider_id"' in migration
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_models.py::test_agent_version_model_has_optional_provider_id tests/test_migrations.py::test_agent_provider_binding_migration_exists -q
```

Expected: FAIL because the column and migration do not exist.

**Step 3: Implement model**

In `app/models/agents.py`, add `provider_id` to `AgentVersion`:

```python
provider_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
```

Place it near the existing `model` and `model_config` columns so the version's model binding fields stay together.

**Step 4: Implement migration**

Create `migrations/versions/20260526_0005_add_agent_provider_binding.py`:

```python
"""add agent provider binding

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
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_versions", "provider_id")
```

**Step 5: Run tests and Alembic heads**

Run:

```bash
uv run python -m pytest tests/test_agent_models.py tests/test_migrations.py -q
uv run alembic heads
```

Expected: PASS, and Alembic reports `20260526_0005 (head)`.

**Step 6: Commit**

```bash
git add app/models/agents.py migrations/versions/20260526_0005_add_agent_provider_binding.py tests/test_agent_models.py tests/test_migrations.py
git commit -m "feat: add provider id to agent versions"
```

### Task 3: Copy Draft Provider Binding During Publish

**Files:**
- Modify: `app/repositories/agents.py`
- Modify: `app/repositories/runs.py`
- Test: `tests/test_agent_repository.py`
- Test: `tests/test_agent_test_runs.py`

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
            model="gpt-4.1-mini",
            provider_id=provider_id,
        ),
    )

    version = await repository.publish_agent("release-reviewer")

    assert version.provider_id == provider_id
```

Import `uuid4` if needed.

**Step 2: Write failing run snapshot test**

Add to `tests/test_agent_test_runs.py`:

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
```

If this file uses a real `RunRepository` instead of fake storage for this behavior, add the assertion to the existing `test_create_agent_test_run_persists_agent_test_payload`.

**Step 3: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_repository.py::test_publish_agent_copies_provider_id_from_draft tests/test_agent_test_runs.py -q
```

Expected: FAIL because publish and snapshot code do not copy `provider_id`.

**Step 4: Implement publish copy**

In `app/repositories/agents.py`, update `publish_agent`:

```python
version = AgentVersion(
    agent_id=agent.id,
    version_number=await self._next_version_number(agent.id),
    system_prompt=draft.system_prompt,
    model=draft.model,
    provider_id=draft.provider_id,
    model_config=dict(draft.model_parameters),
    tool_allowlist=list(draft.tool_allowlist),
    mcp_server_ids=list(draft.mcp_server_ids),
    published_by=published_by,
)
```

**Step 5: Implement run snapshot copy**

In `app/repositories/runs.py`, update `_agent_version_snapshot`:

```python
provider_id = getattr(agent_version, "provider_id", None)
if provider_id is not None:
    snapshot["provider_id"] = str(provider_id)
```

**Step 6: Run tests**

Run:

```bash
uv run python -m pytest tests/test_agent_repository.py tests/test_agent_test_runs.py -q
```

Expected: PASS, with DB tests skipped unless `TEST_DATABASE_URL` is set.

**Step 7: Commit**

```bash
git add app/repositories/agents.py app/repositories/runs.py tests/test_agent_repository.py tests/test_agent_test_runs.py
git commit -m "feat: snapshot agent provider binding"
```

### Task 4: Store Optional Test-Run User Context

**Files:**
- Modify: `app/api/v1/agents.py`
- Modify: `app/services/agents.py`
- Modify: `app/repositories/runs.py`
- Test: `tests/test_agent_test_runs.py`
- Test: `tests/test_agents_api.py`

**Step 1: Write failing service/repository test**

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

**Step 2: Write failing API compatibility test**

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

**Step 4: Update service signature**

In `app/services/agents.py`, import `CurrentUser`:

```python
from app.api.auth import CurrentUser
```

Update `AgentService.start_test_run`:

```python
async def start_test_run(
    self,
    agent_key: str,
    request: AgentTestRunCreate,
    current_user: CurrentUser | None = None,
) -> AgentRunStartResult:
```

Before calling `create_agent_test_run`, build:

```python
current_user_payload = (
    {"user_id": current_user.user_id, "role": current_user.role}
    if current_user is not None
    else None
)
```

Pass `current_user=current_user_payload` and `created_by=current_user.user_id if current_user else None` to `create_agent_test_run`.

**Step 5: Update route**

In `app/api/v1/agents.py`, before constructing the service:

```python
current_user = getattr(request.state, "current_user", None)
```

Call:

```python
result = await service.start_test_run(agent_key, payload, current_user=current_user)
```

Do not use `CurrentUserDep`; headers are optional.

**Step 6: Update run repository**

In `app/repositories/runs.py`, add parameter:

```python
current_user: dict[str, str] | None = None,
```

Store it in both `metadata_` and `subject_snapshot` only when present:

```python
metadata = {
    ...
}
subject_snapshot = {
    "messages": [dict(message) for message in messages],
    "agent_version": _agent_version_snapshot(agent_version),
}
if current_user is not None:
    metadata["current_user"] = dict(current_user)
    subject_snapshot["current_user"] = dict(current_user)
```

Pass those locals into the `Run(...)` constructor.

**Step 7: Run tests**

Run:

```bash
uv run python -m pytest tests/test_agent_test_runs.py tests/test_agents_api.py -q
```

Expected: PASS.

**Step 8: Commit**

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
    ):
        self.provider = provider
        self.base_url = base_url
        self.api_key_ciphertext = api_key_ciphertext


class FakeProviderResolver:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    async def resolve(self, provider_id, user_id):
        self.calls.append((provider_id, user_id))
        return self.provider


async def test_runtime_resolves_provider_when_version_has_provider_id() -> None:
    provider_id = uuid4()
    resolver = FakeProviderResolver(FakeProvider())
    factory = FakeModelFactory()
    runtime = AgentRuntime(model_factory=factory, provider_resolver=resolver)
    version = FakeVersion(provider_id=provider_id)

    await runtime.run(
        version=version,
        messages=[{"role": "user", "content": "Hi"}],
        current_user={"user_id": "user-123", "role": "user"},
    )

    assert resolver.calls == [(provider_id, "user-123")]
    assert factory.calls[0]["model"] == version.model
    assert factory.calls[0]["kwargs"]["api_key"] == "sk-test123456"
    assert factory.calls[0]["kwargs"]["base_url"] == "https://api.openai.com/v1"
```

Update `FakeModelFactory` in the test file if needed so it records `kwargs`.

Add a legacy assertion:

```python
async def test_runtime_without_provider_id_keeps_legacy_model_factory_call() -> None:
    resolver = FakeProviderResolver(FakeProvider())
    factory = FakeModelFactory()
    runtime = AgentRuntime(model_factory=factory, provider_resolver=resolver)

    await runtime.run(version=FakeVersion(provider_id=None), messages=[])

    assert resolver.calls == []
```

**Step 2: Write failing repository resolution tests**

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

In `app/repositories/provider_credentials.py`, import `or_`:

```python
from sqlalchemy import or_, select
```

Add:

```python
async def get_runtime_llm_provider(
    self,
    provider_id: UUID,
    owner_user_id: str | None,
) -> ProviderCredential | None:
    statement = (
        self._active_llm_provider_statement()
        .where(ProviderCredential.id == provider_id)
        .where(
            or_(
                (ProviderCredential.scope == "global")
                & ProviderCredential.owner_user_id.is_(None),
                (ProviderCredential.scope == "user")
                & (ProviderCredential.owner_user_id == owner_user_id)
                if owner_user_id is not None
                else False,
            )
        )
        .limit(1)
    )
    return await self._session.scalar(statement)
```

If SQLAlchemy rejects `False` in `or_`, build conditions as a list and append the user condition only when `owner_user_id` is not None.

**Step 5: Add runtime provider resolver protocol**

In `agent/react_runtime.py`, add:

```python
class RuntimeProviderUnavailableError(RuntimeError):
    pass


class NullProviderResolver:
    async def resolve(self, provider_id, user_id):
        raise RuntimeProviderUnavailableError(
            f"LLM provider is not available: {provider_id}"
        )
```

Update `AgentRuntime.__init__`:

```python
provider_resolver=None,
```

Store:

```python
self._provider_resolver = provider_resolver or NullProviderResolver()
```

Update `run` signature:

```python
current_user: dict[str, str] | None = None,
```

Before model creation:

```python
model_kwargs = dict(model_config)
provider_id = getattr(version, "provider_id", None)
if provider_id is not None:
    user_id = current_user.get("user_id") if current_user else None
    provider = await self._provider_resolver.resolve(provider_id, user_id)
    model_kwargs.update(_provider_model_kwargs(provider))
model = self._model_factory(version.model, **model_kwargs)
```

Add helper:

```python
def _provider_model_kwargs(provider: Any) -> dict[str, Any]:
    kwargs = {"api_key": provider.api_key_ciphertext}
    if provider.base_url:
        kwargs["base_url"] = provider.base_url
    if provider.provider:
        kwargs["model_provider"] = provider.provider
    return kwargs
```

**Step 6: Wire resolver into executor**

In `app/services/agents.py`, import `ProviderCredentialRepository`.

Add a small adapter:

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

Update `run_agent_test` signature:

```python
provider_repository: ProviderCredentialRepository | None = None,
```

When creating the default runtime:

```python
if runtime is None:
    resolver = (
        ProviderCredentialRuntimeResolver(provider_repository)
        if provider_repository is not None
        else None
    )
    runtime = AgentRuntime(provider_resolver=resolver)
```

Pass current user:

```python
result = await runtime.run(
    version=version,
    messages=list(run.subject_snapshot.get("messages", [])),
    current_user=run.subject_snapshot.get("current_user"),
)
```

Update `run_agent_test_with_new_session`:

```python
provider_repository = ProviderCredentialRepository(session)
return await run_agent_test(
    run_id,
    run_repository,
    agent_repository,
    provider_repository=provider_repository,
)
```

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

### Task 6: Update API Contract And Final Verification

**Files:**
- Modify: `api/openapi.yml`
- Modify: `README.md` only if the existing local README change is intended for this feature; otherwise leave it unstaged.
- Test: relevant test files from earlier tasks.

**Step 1: Check contract coverage**

Run:

```bash
uv run python -m pytest tests/test_openapi_contract.py -q
```

Expected: PASS.

If it fails because new schemas differ from the contract, update `api/openapi.yml` and rerun.

**Step 2: Run focused backend tests**

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

**Step 3: Run full tests**

Run:

```bash
uv run python -m pytest -q
```

Expected: PASS.

**Step 4: Verify Alembic graph**

Run:

```bash
uv run alembic heads
```

Expected:

```text
20260526_0005 (head)
```

**Step 5: Final status check**

Run:

```bash
git status --short
```

Expected: only intentional files changed. Do not stage unrelated `README.md` unless the user explicitly asks.

**Step 6: Commit any final contract/test adjustments**

If Task 6 changed files:

```bash
git add api/openapi.yml tests/test_openapi_contract.py
git commit -m "test: cover agent provider binding contract"
```

If no files changed, skip this commit.

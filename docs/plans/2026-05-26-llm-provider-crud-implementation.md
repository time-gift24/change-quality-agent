# LLM Provider CRUD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build backend CRUD APIs for user-owned and admin-managed global LLM provider credentials, with fake auth middleware that can later be replaced by SSO.

**Architecture:** Store credentials in one generic `provider_credentials` table, separated by `credential_type`, `scope`, and `owner_user_id`. User routes operate only on the current user's `llm_provider` records; admin routes operate only on global `llm_provider` records. Fake auth middleware reads request headers and dependencies enforce user/admin access.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL JSONB, pytest, httpx.

Use @fastapi and @project-structure while implementing. Keep the work inside the feature worktree; do not edit the main branch path. Do not commit `.agents/` or `skills-lock.json`.

---

### Task 1: Repair the Alembic Revision Graph

Current baseline warning:

```bash
uv run alembic heads
```

Expected current output before this task:

```text
UserWarning: Revision 20260526_0002 is present more than once
20260526_0002 (head)
20260526_0002 (head)
```

The provider credentials migration should not be added until revision IDs are unique.

**Files:**
- Create: `tests/test_migrations.py`
- Rename: `migrations/versions/20260526_0002_create_agents.py` -> `migrations/versions/20260526_0003_create_agents.py`
- Modify: `migrations/versions/20260526_0003_create_agents.py`

**Step 1: Write the failing test**

Create `tests/test_migrations.py`:

```python
import re
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"
REVISION_RE = re.compile(r'^revision: str = "([^"]+)"$', re.MULTILINE)


def test_alembic_revision_ids_are_unique() -> None:
    revisions: dict[str, Path] = {}
    duplicates: list[str] = []

    for path in MIGRATIONS_DIR.glob("*.py"):
        match = REVISION_RE.search(path.read_text(encoding="utf-8"))
        assert match is not None, f"{path.name} does not define revision"
        revision = match.group(1)
        if revision in revisions:
            duplicates.append(revision)
        revisions[revision] = path

    assert duplicates == []
```

**Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_migrations.py::test_alembic_revision_ids_are_unique -v
```

Expected: FAIL with duplicate `20260526_0002`.

**Step 3: Linearize the existing duplicate revisions**

If this repository has already applied either duplicate `20260526_0002`
migration to a shared database, stop before editing revision IDs and coordinate
a migration repair strategy.

Rename the agents migration file:

```bash
mv migrations/versions/20260526_0002_create_agents.py migrations/versions/20260526_0003_create_agents.py
```

Update the header in `migrations/versions/20260526_0003_create_agents.py`:

```python
"""create agents

Revision ID: 20260526_0003
Revises: 20260526_0002
Create Date: 2026-05-26

"""

revision: str = "20260526_0003"
down_revision: str | Sequence[str] | None = "20260526_0002"
```

Keep `migrations/versions/20260526_0002_create_mcp_servers.py` as the
`20260526_0002` revision after `20260525_0001`.

**Step 4: Verify the migration graph**

Run:

```bash
uv run pytest tests/test_migrations.py::test_alembic_revision_ids_are_unique -v
uv run alembic heads
```

Expected: test passes and Alembic reports a single head, `20260526_0003 (head)`, with no duplicate revision warning.

**Step 5: Commit**

```bash
git add -A migrations/versions tests/test_migrations.py
git commit -m "fix: make alembic revisions unique"
```

### Task 2: Add Fake Auth Middleware and Dependencies

**Files:**
- Create: `app/api/auth.py`
- Modify: `app/api/deps.py`
- Modify: `app/main.py`
- Test: `tests/test_auth.py`

**Step 1: Write the failing tests**

Create `tests/test_auth.py`:

```python
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.auth import (
    CurrentUser,
    fake_auth_middleware,
    get_current_user,
    require_admin_user,
)


def build_probe_app() -> FastAPI:
    probe = FastAPI()
    probe.middleware("http")(fake_auth_middleware)

    @probe.get("/me")
    async def me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {"user_id": user.user_id, "role": user.role}

    @probe.get("/admin")
    async def admin(
        user: CurrentUser = Depends(require_admin_user),
    ) -> dict[str, str]:
        return {"user_id": user.user_id, "role": user.role}

    return probe


@pytest.mark.asyncio
async def test_fake_auth_middleware_attaches_current_user() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=build_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/me",
            headers={"x-user-id": "user-123", "x-user-role": "admin"},
        )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123", "role": "admin"}


@pytest.mark.asyncio
async def test_current_user_dependency_requires_user_id() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=build_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_dependency_requires_admin_role() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=build_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/admin",
            headers={"x-user-id": "user-123", "x-user-role": "user"},
        )

    assert response.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_auth.py -v
```

Expected: FAIL because `app.api.auth` does not exist.

**Step 3: Implement auth helpers**

Create `app/api/auth.py`:

```python
from dataclasses import dataclass
from typing import Annotated

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: str = "user"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


async def fake_auth_middleware(request: Request, call_next):
    user_id = request.headers.get("x-user-id")
    role = request.headers.get("x-user-role") or "user"
    request.state.current_user = (
        CurrentUser(user_id=user_id, role=role) if user_id else None
    )
    return await call_next(request)


def get_current_user(request: Request) -> CurrentUser:
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


def require_admin_user(request: Request) -> CurrentUser:
    user = get_current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user
```

Modify `app/api/deps.py`:

```python
from app.api.auth import CurrentUser, get_current_user, require_admin_user

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin_user)]
```

Modify `app/main.py` after app creation:

```python
from app.api.auth import fake_auth_middleware

app = FastAPI(title="Change Quality Agent", lifespan=lifespan)
app.middleware("http")(fake_auth_middleware)
```

The middleware only attaches identity. Route dependencies decide which endpoints require identity, so existing public endpoints stay compatible.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_auth.py tests/test_api_dependencies.py tests/test_app.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/auth.py app/api/deps.py app/main.py tests/test_auth.py
git commit -m "feat: add fake auth context"
```

### Task 3: Define LLM Provider Schemas and Secret Helpers

**Files:**
- Create: `app/schemas/llm_providers.py`
- Create: `app/services/provider_credentials.py`
- Test: `tests/test_llm_provider_schemas.py`

**Step 1: Write the failing tests**

Create `tests/test_llm_provider_schemas.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
    LlmProviderUpdate,
)
from app.services.provider_credentials import api_key_hint, prepare_api_key


def test_create_schema_accepts_openai_compatible_provider() -> None:
    payload = LlmProviderCreate(
        name="OpenAI personal",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test123456",
        model="gpt-4.1-mini",
        metadata={"team": "qa"},
    )

    assert payload.provider == "openai"
    assert payload.metadata == {"team": "qa"}


def test_update_schema_allows_partial_payload() -> None:
    payload = LlmProviderUpdate(model="gpt-5-mini")

    assert payload.model == "gpt-5-mini"
    assert payload.api_key is None


def test_detail_schema_never_exposes_api_key() -> None:
    detail = LlmProviderDetail(
        id=uuid4(),
        name="OpenAI personal",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key_hint="sk-...3456",
        model="gpt-4.1-mini",
        metadata={},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    dumped = detail.model_dump()

    assert "api_key" not in dumped
    assert "api_key_ciphertext" not in dumped


def test_api_key_hint_masks_secret() -> None:
    assert api_key_hint("sk-test123456") == "sk-...3456"
    assert api_key_hint("short") == "********"


def test_prepare_api_key_returns_ciphertext_and_hint() -> None:
    prepared = prepare_api_key("sk-test123456")

    assert prepared.ciphertext == "sk-test123456"
    assert prepared.hint == "sk-...3456"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_llm_provider_schemas.py -v
```

Expected: FAIL because schema and service modules do not exist.

**Step 3: Implement schemas and helpers**

Create `app/services/provider_credentials.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedApiKey:
    ciphertext: str
    hint: str


def api_key_hint(api_key: str) -> str:
    if len(api_key) < 8:
        return "********"
    return f"{api_key[:3]}...{api_key[-4:]}"


def prepare_api_key(api_key: str) -> PreparedApiKey:
    # v1 keeps the storage helper replaceable for future KMS integration.
    return PreparedApiKey(ciphertext=api_key, hint=api_key_hint(api_key))
```

Create `app/schemas/llm_providers.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LlmProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str = Field(min_length=1)
    model: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LlmProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_active: bool | None = None


class LlmProviderDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider: str | None = None
    base_url: str | None = None
    api_key_hint: str
    model: str | None = None
    metadata: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_llm_provider_schemas.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/schemas/llm_providers.py app/services/provider_credentials.py tests/test_llm_provider_schemas.py
git commit -m "feat: add llm provider schemas"
```

### Task 4: Add Provider Credential Model and Migration

**Files:**
- Create: `app/models/provider_credentials.py`
- Modify: `app/models/__init__.py`
- Create: `migrations/versions/20260526_0004_create_provider_credentials.py`
- Modify: `tests/test_models.py`
- Test: `tests/test_migrations.py`

**Step 1: Write failing model tests**

Append to `tests/test_models.py`:

```python
from app.models.provider_credentials import ProviderCredential


def test_provider_credential_model_table_name() -> None:
    assert ProviderCredential.__tablename__ == "provider_credentials"


def test_provider_credential_model_has_scope_and_secret_columns() -> None:
    columns = ProviderCredential.__table__.columns

    assert "credential_type" in columns
    assert "scope" in columns
    assert "owner_user_id" in columns
    assert "api_key_ciphertext" in columns
    assert "api_key_hint" in columns
    assert "is_active" in columns
```

Append to `tests/test_migrations.py`:

```python
def test_provider_credentials_migration_exists() -> None:
    migration = MIGRATIONS_DIR / "20260526_0004_create_provider_credentials.py"

    assert migration.exists()
    content = migration.read_text(encoding="utf-8")
    assert 'revision: str = "20260526_0004"' in content
    assert 'down_revision: str | Sequence[str] | None = "20260526_0003"' in content
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_models.py tests/test_migrations.py -v
```

Expected: FAIL because the model and migration do not exist.

**Step 3: Implement the SQLAlchemy model**

Create `app/models/provider_credentials.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'user' AND owner_user_id IS NOT NULL) OR "
            "(scope = 'global' AND owner_user_id IS NULL)",
            name="ck_provider_credentials_scope_owner",
        ),
        CheckConstraint(
            "credential_type IN ('llm_provider', 'api_key')",
            name="ck_provider_credentials_type",
        ),
        CheckConstraint(
            "scope IN ('user', 'global')",
            name="ck_provider_credentials_scope",
        ),
        Index(
            "uq_provider_credentials_user_active_name",
            "credential_type",
            "owner_user_id",
            "name",
            unique=True,
            postgresql_where=text("scope = 'user' AND is_active"),
        ),
        Index(
            "uq_provider_credentials_global_active_name",
            "credential_type",
            "name",
            unique=True,
            postgresql_where=text("scope = 'global' AND is_active"),
        ),
        Index(
            "ix_provider_credentials_lookup",
            "credential_type",
            "scope",
            "owner_user_id",
            "is_active",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    base_url: Mapped[str | None] = mapped_column(Text)
    api_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hint: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_by: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
```

**Step 4: Implement the Alembic migration**

Create `migrations/versions/20260526_0004_create_provider_credentials.py` with
the same columns, check constraints, and indexes as the model. Use:

```python
revision: str = "20260526_0004"
down_revision: str | Sequence[str] | None = "20260526_0003"
```

Add `server_default=sa.text("'{}'::jsonb")` for `metadata` and
`server_default=sa.text("true")` for `is_active`.

**Step 5: Verify model and migration tests**

Run:

```bash
uv run pytest tests/test_models.py tests/test_migrations.py -v
uv run alembic heads
```

Expected: PASS, and Alembic reports `20260526_0004 (head)`.

**Step 6: Commit**

```bash
git add app/models/provider_credentials.py app/models/__init__.py migrations/versions/20260526_0004_create_provider_credentials.py tests/test_models.py tests/test_migrations.py
git commit -m "feat: add provider credential model"
```

### Task 5: Add Provider Credential Repository

**Files:**
- Create: `app/repositories/provider_credentials.py`
- Modify: `app/api/deps.py`
- Test: `tests/test_provider_credential_repository.py`
- Test: `tests/test_api_dependencies.py`

**Step 1: Write failing repository integration tests**

Create `tests/test_provider_credential_repository.py` using the same `TEST_DATABASE_URL`
skip pattern as `tests/test_mcp_repository.py`.

Cover these tests:

```python
async def test_user_provider_crud_is_scoped_to_owner(session) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(
        scope="user",
        owner_user_id="user-1",
        name="OpenAI",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key_ciphertext="sk-user1",
        api_key_hint="sk-...ser1",
        model="gpt-4.1-mini",
        metadata_={},
        actor_user_id="user-1",
    )

    assert await repository.get_user_llm_provider(provider.id, "user-1") is not None
    assert await repository.get_user_llm_provider(provider.id, "user-2") is None
```

Also cover:

- `list_user_llm_providers` returns only active records for the owner.
- `list_global_llm_providers` returns only active global records.
- `soft_delete_user_llm_provider` hides a record from user reads.
- `update_user_llm_provider` changes only provided fields.

Append to `tests/test_api_dependencies.py`:

```python
from app.api.deps import get_provider_credential_repository
from app.repositories.provider_credentials import ProviderCredentialRepository


def test_provider_credential_repository_dependency_uses_session() -> None:
    session = object()

    repository = get_provider_credential_repository(session)

    assert isinstance(repository, ProviderCredentialRepository)
    assert repository._session is session
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_provider_credential_repository.py tests/test_api_dependencies.py -v
```

Expected: dependency test fails because the repository does not exist. DB tests are skipped unless `TEST_DATABASE_URL` is set.

**Step 3: Implement repository**

Create `app/repositories/provider_credentials.py` with:

```python
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_credentials import ProviderCredential


class ProviderCredentialNameExistsError(Exception):
    pass


class ProviderCredentialNotFoundError(Exception):
    pass


class ProviderCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_llm_provider(self, **values: Any) -> ProviderCredential:
        values["credential_type"] = "llm_provider"
        credential = ProviderCredential(**values)
        self._session.add(credential)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ProviderCredentialNameExistsError() from exc
        return credential
```

Then add scoped helpers:

```python
async def list_user_llm_providers(self, owner_user_id: str) -> list[ProviderCredential]
async def list_global_llm_providers(self) -> list[ProviderCredential]
async def get_user_llm_provider(self, provider_id: UUID, owner_user_id: str) -> ProviderCredential | None
async def get_global_llm_provider(self, provider_id: UUID) -> ProviderCredential | None
async def update_user_llm_provider(self, provider_id: UUID, owner_user_id: str, **values: Any) -> ProviderCredential
async def update_global_llm_provider(self, provider_id: UUID, **values: Any) -> ProviderCredential
async def soft_delete_user_llm_provider(self, provider_id: UUID, owner_user_id: str, *, updated_by: str) -> ProviderCredential
async def soft_delete_global_llm_provider(self, provider_id: UUID, *, updated_by: str) -> ProviderCredential
async def commit(self) -> None
```

All list/get methods must include:

```python
ProviderCredential.credential_type == "llm_provider"
ProviderCredential.is_active.is_(True)
```

User methods must also include `scope == "user"` and `owner_user_id == owner_user_id`.
Global methods must include `scope == "global"` and `owner_user_id.is_(None)`.

Soft delete sets `is_active = False` and `updated_by = updated_by`.

**Step 4: Add dependency wiring**

Modify `app/api/deps.py`:

```python
from app.repositories.provider_credentials import ProviderCredentialRepository


def get_provider_credential_repository(
    session: SessionDep,
) -> ProviderCredentialRepository:
    return ProviderCredentialRepository(session)


ProviderCredentialRepositoryDep = Annotated[
    ProviderCredentialRepository,
    Depends(get_provider_credential_repository),
]
```

**Step 5: Verify tests**

Run:

```bash
uv run pytest tests/test_provider_credential_repository.py tests/test_api_dependencies.py -v
```

Expected: PASS for non-DB tests; DB tests pass when `TEST_DATABASE_URL` is set and skip otherwise.

**Step 6: Commit**

```bash
git add app/repositories/provider_credentials.py app/api/deps.py tests/test_provider_credential_repository.py tests/test_api_dependencies.py
git commit -m "feat: add provider credential repository"
```

### Task 6: Add User LLM Provider API

**Files:**
- Create: `app/api/v1/llm_providers.py`
- Modify: `app/main.py`
- Test: `tests/test_llm_providers_api.py`

**Step 1: Write failing API tests**

Create `tests/test_llm_providers_api.py` with fake repository/session patterns from `tests/test_agents_api.py`.

Required tests:

```python
@pytest.mark.asyncio
async def test_user_provider_routes_require_auth() -> None:
    override_dependencies(FakeProviderRepository(), FakeSession())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/llm-providers")

    assert response.status_code == 401
```

```python
@pytest.mark.asyncio
async def test_create_user_provider_for_current_user_and_redacts_api_key() -> None:
    repository = FakeProviderRepository()
    session = FakeSession()
    override_dependencies(repository, session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/llm-providers",
            headers={"x-user-id": "user-1"},
            json={
                "name": "OpenAI",
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-user123456",
                "model": "gpt-4.1-mini",
                "metadata": {},
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["api_key_hint"] == "sk-...3456"
    assert "api_key" not in body
    assert "api_key_ciphertext" not in body
    assert repository.created_values["scope"] == "user"
    assert repository.created_values["owner_user_id"] == "user-1"
    assert session.commits == 1
```

Also cover:

- `GET /api/llm-providers` lists current user records.
- `GET /api/llm-providers/{id}` returns `404` when repository returns `None`.
- `PATCH` without `api_key` does not pass secret fields to repository.
- `PATCH` with `api_key` updates secret fields and hint.
- `DELETE` calls soft delete and returns `204`.
- Repository name conflict maps to `409`.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_llm_providers_api.py -v
```

Expected: FAIL because the route does not exist.

**Step 3: Implement user routes**

Create `app/api/v1/llm_providers.py`:

```python
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import (
    CurrentUserDep,
    ProviderCredentialRepositoryDep,
)
from app.repositories.provider_credentials import (
    ProviderCredentialNameExistsError,
    ProviderCredentialNotFoundError,
)
from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
    LlmProviderUpdate,
)
from app.services.provider_credentials import prepare_api_key

router = APIRouter(prefix="/api/llm-providers", tags=["llm-providers"])
```

Implement:

```python
@router.get("")
async def list_llm_providers(
    current_user: CurrentUserDep,
    repository: ProviderCredentialRepositoryDep,
) -> list[LlmProviderDetail]:
    providers = await repository.list_user_llm_providers(current_user.user_id)
    return [_provider_detail(provider) for provider in providers]
```

Implement create/update/delete using repository methods and `await repository.commit()`.
Map `ProviderCredentialNameExistsError` to `409`.
Map `ProviderCredentialNotFoundError` or `None` to `404`.

Use a helper:

```python
def _provider_detail(provider) -> LlmProviderDetail:
    return LlmProviderDetail(
        id=provider.id,
        name=provider.name,
        provider=provider.provider,
        base_url=provider.base_url,
        api_key_hint=provider.api_key_hint,
        model=provider.model,
        metadata=provider.metadata_,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )
```

For update payloads:

```python
values = payload.model_dump(exclude_unset=True)
api_key = values.pop("api_key", None)
if api_key is not None:
    prepared = prepare_api_key(api_key)
    values["api_key_ciphertext"] = prepared.ciphertext
    values["api_key_hint"] = prepared.hint
if "metadata" in values:
    values["metadata_"] = values.pop("metadata")
```

**Step 4: Register the router**

Modify `app/main.py`:

```python
from app.api.v1 import agents, llm_providers, mcp, runs, sop

app.include_router(llm_providers.router)
```

**Step 5: Verify tests**

Run:

```bash
uv run pytest tests/test_llm_providers_api.py tests/test_auth.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/api/v1/llm_providers.py app/main.py tests/test_llm_providers_api.py
git commit -m "feat: add user llm provider api"
```

### Task 7: Add Admin LLM Provider API

**Files:**
- Create: `app/api/v1/admin_llm_providers.py`
- Modify: `app/main.py`
- Test: `tests/test_admin_llm_providers_api.py`

**Step 1: Write failing tests**

Create `tests/test_admin_llm_providers_api.py` with the same fake repository/session helpers as the user API test.

Required tests:

- Non-admin user receives `403` for `GET /api/admin/llm-providers`.
- Missing user receives `401`.
- Admin create sets `scope = global` and `owner_user_id = None`.
- Admin list returns only repository global records.
- Admin get returns `404` when missing.
- Admin patch maps duplicate name to `409`.
- Admin delete soft-deletes and returns `204`.
- Responses never include `api_key` or `api_key_ciphertext`.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_admin_llm_providers_api.py -v
```

Expected: FAIL because route does not exist.

**Step 3: Implement admin routes**

Create `app/api/v1/admin_llm_providers.py`:

```python
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AdminUserDep, ProviderCredentialRepositoryDep
from app.repositories.provider_credentials import (
    ProviderCredentialNameExistsError,
    ProviderCredentialNotFoundError,
)
from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
    LlmProviderUpdate,
)
from app.services.provider_credentials import prepare_api_key
```

Use:

```python
router = APIRouter(prefix="/api/admin/llm-providers", tags=["admin-llm-providers"])
```

Admin create must call:

```python
await repository.create_llm_provider(
    scope="global",
    owner_user_id=None,
    ...
    created_by=current_user.user_id,
    updated_by=current_user.user_id,
)
```

Admin get/list/update/delete must use the global repository methods.

Avoid duplicating serialization logic by either importing `_provider_detail`
from `app.api.v1.llm_providers` or moving the serializer to a small private
helper module if circular imports appear. Prefer the simplest import that keeps
tests passing.

**Step 4: Register the router**

Modify `app/main.py`:

```python
from app.api.v1 import admin_llm_providers, agents, llm_providers, mcp, runs, sop

app.include_router(admin_llm_providers.router)
```

**Step 5: Verify tests**

Run:

```bash
uv run pytest tests/test_admin_llm_providers_api.py tests/test_llm_providers_api.py tests/test_auth.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/api/v1/admin_llm_providers.py app/main.py tests/test_admin_llm_providers_api.py
git commit -m "feat: add admin llm provider api"
```

### Task 8: Update OpenAPI Contract

**Files:**
- Modify: `api/openapi.yml`
- Modify: `tests/test_openapi_contract.py`

**Step 1: Write failing OpenAPI tests**

Append tests to `tests/test_openapi_contract.py`:

```python
def test_llm_provider_paths_are_documented() -> None:
    contract = load_contract()
    paths = contract["paths"]
    expected_operations = {
        ("/api/llm-providers", "get"): {"200", "401", "422"},
        ("/api/llm-providers", "post"): {"201", "401", "409", "422"},
        ("/api/llm-providers/{provider_id}", "get"): {"200", "401", "404", "422"},
        ("/api/llm-providers/{provider_id}", "patch"): {
            "200",
            "401",
            "404",
            "409",
            "422",
        },
        ("/api/llm-providers/{provider_id}", "delete"): {
            "204",
            "401",
            "404",
            "422",
        },
        ("/api/admin/llm-providers", "get"): {"200", "401", "403", "422"},
        ("/api/admin/llm-providers", "post"): {
            "201",
            "401",
            "403",
            "409",
            "422",
        },
        ("/api/admin/llm-providers/{provider_id}", "get"): {
            "200",
            "401",
            "403",
            "404",
            "422",
        },
        ("/api/admin/llm-providers/{provider_id}", "patch"): {
            "200",
            "401",
            "403",
            "404",
            "409",
            "422",
        },
        ("/api/admin/llm-providers/{provider_id}", "delete"): {
            "204",
            "401",
            "403",
            "404",
            "422",
        },
    }

    for (path, method), statuses in expected_operations.items():
        operation = paths[path][method]
        assert statuses <= set(operation["responses"])


def test_llm_provider_schemas_do_not_expose_secrets() -> None:
    schemas = load_contract()["components"]["schemas"]

    for schema_name in ("LlmProviderCreate", "LlmProviderUpdate", "LlmProviderDetail"):
        assert schema_name in schemas

    detail_properties = schemas["LlmProviderDetail"]["properties"]
    assert "api_key_hint" in detail_properties
    assert "api_key" not in detail_properties
    assert "api_key_ciphertext" not in detail_properties
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -v
```

Expected: FAIL because contract does not include LLM provider paths and schemas.

**Step 3: Update `api/openapi.yml`**

Add tags:

```yaml
  - name: llm-providers
    description: User-owned LLM provider credentials.
  - name: admin-llm-providers
    description: Admin-managed global LLM provider credentials.
```

Add reusable parameter:

```yaml
    ProviderId:
      name: provider_id
      in: path
      required: true
      schema:
        type: string
        format: uuid
```

Add security scheme:

```yaml
    FakeUserHeaders:
      type: apiKey
      in: header
      name: X-User-Id
    FakeUserRole:
      type: apiKey
      in: header
      name: X-User-Role
```

Add schemas for `LlmProviderCreate`, `LlmProviderUpdate`, and
`LlmProviderDetail`. Only create/update schemas include `api_key`; detail must
only include `api_key_hint`.

Document all user and admin paths from the tests. Set `security` to:

```yaml
security:
  - FakeUserHeaders: []
```

for user LLM provider operations, and:

```yaml
security:
  - FakeUserHeaders: []
  - FakeUserRole: []
```

for admin LLM provider operations.

**Step 4: Verify OpenAPI tests**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add api/openapi.yml tests/test_openapi_contract.py
git commit -m "docs: document llm provider api"
```

### Task 9: Final Verification

**Files:**
- Verify all touched files.

**Step 1: Run focused tests**

Run:

```bash
uv run pytest \
  tests/test_auth.py \
  tests/test_llm_provider_schemas.py \
  tests/test_models.py \
  tests/test_migrations.py \
  tests/test_provider_credential_repository.py \
  tests/test_llm_providers_api.py \
  tests/test_admin_llm_providers_api.py \
  tests/test_api_dependencies.py \
  tests/test_openapi_contract.py \
  -v
```

Expected: PASS, with repository integration tests skipped unless `TEST_DATABASE_URL`
is configured.

**Step 2: Run full backend test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

**Step 3: Verify Alembic graph**

Run:

```bash
uv run alembic heads
```

Expected: one head, `20260526_0004 (head)`, with no duplicate revision warning.

**Step 4: Check git diff**

Run:

```bash
git status --short
git diff --check
```

Expected: only intended files changed before the final commit; `git diff --check`
exits 0.

**Step 5: Final commit if any verification-only edits remain**

If files remain unstaged after the earlier task commits:

```bash
git add <remaining-files>
git commit -m "test: verify llm provider crud"
```

Do not make this commit if there are no remaining changes.

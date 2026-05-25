# ReAct Agent CRUD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build backend CRUD, draft publishing, immutable versions, and persisted test runs for ReAct agents.

**Architecture:** Add an Agent Registry beside the existing SOP flow. Store editable draft state in `agents`, immutable runnable snapshots in `agent_versions`, and execute tests through the existing `runs` and `run_events` substrate. Wrap `langchain.agents.create_agent` behind `agent/react_runtime.py` so future tool, MCP, and dynamic-node modules can replace the resolver layer without changing the HTTP contract.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async ORM, Alembic, PostgreSQL JSONB, LangChain `create_agent`, existing `RunRepository` and SSE run observation APIs.

---

## Pre-Flight

Use the existing worktree:

```bash
cd /Users/wanyaozhong/Projects/change-quality-agent/.worktrees/react-agent-crud-design
git branch --show-current
```

Expected: `codex/react-agent-crud-design`.

Reference skills while implementing:

- @fastapi for API and Pydantic style.
- @project-structure for placement.
- @superpowers:test-driven-development for each task.
- @superpowers:verification-before-completion before claiming done.

Run baseline:

```bash
uv run pytest
```

Expected: existing suite passes, with DB-marked tests skipped unless
`TEST_DATABASE_URL` is configured.

---

### Task 1: Add Agent Schemas

**Files:**

- Create: `app/schemas/agents.py`
- Modify: `app/schemas/__init__.py`
- Test: `tests/test_agent_schemas.py`

**Step 1: Write failing schema tests**

Create `tests/test_agent_schemas.py`:

```python
from app.schemas.agents import AgentCreate, AgentDraftConfig, AgentTestRunCreate


def test_agent_create_accepts_initial_draft() -> None:
    request = AgentCreate(
        key="release-reviewer",
        display_name="Release Reviewer",
        description="Checks release quality",
        draft=AgentDraftConfig(
            system_prompt="You are careful.",
            model="openai:gpt-5-mini",
            model_config={"temperature": 0},
            tool_allowlist=["search_sop"],
            mcp_server_ids=["change-docs"],
        ),
    )

    assert request.key == "release-reviewer"
    assert request.draft.model == "openai:gpt-5-mini"


def test_agent_test_run_requires_messages() -> None:
    request = AgentTestRunCreate(
        messages=[{"role": "user", "content": "Review this change."}]
    )

    assert request.messages[0].role == "user"
    assert request.version_number is None
```

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_agent_schemas.py -v
```

Expected: import failure for `app.schemas.agents`.

**Step 3: Implement schemas**

Create `app/schemas/agents.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentDraftConfig(BaseModel):
    system_prompt: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_config: dict[str, Any] = Field(default_factory=dict)
    tool_allowlist: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)


class AgentCreate(BaseModel):
    key: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=1)
    description: str | None = None
    draft: AgentDraftConfig


class AgentDraftUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    enabled: bool | None = None
    draft: AgentDraftConfig | None = None


class AgentVersionSummary(BaseModel):
    id: UUID
    version_number: int
    model: str
    published_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentSummary(BaseModel):
    id: UUID
    key: str
    display_name: str
    description: str | None = None
    enabled: bool
    has_draft: bool
    latest_version: AgentVersionSummary | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentDetail(AgentSummary):
    draft: AgentDraftConfig | None = None


class AgentVersionDetail(AgentVersionSummary):
    agent_id: UUID
    system_prompt: str
    model_config_payload: dict[str, Any] = Field(alias="model_config")
    tool_allowlist: list[str]
    mcp_server_ids: list[str]
    published_by: str | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant|system)$")
    content: str = Field(min_length=1)


class AgentTestRunCreate(BaseModel):
    version_id: UUID | None = None
    version_number: int | None = Field(default=None, ge=1)
    messages: list[AgentMessage] = Field(min_length=1)
```

Update `app/schemas/__init__.py` only if this project exports schemas there.
If it is intentionally empty, leave it alone.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/test_agent_schemas.py -v
```

Expected: pass.

**Step 5: Commit**

```bash
git add app/schemas/agents.py app/schemas/__init__.py tests/test_agent_schemas.py
git commit -m "feat: add agent API schemas"
```

---

### Task 2: Add Agent ORM Models and Migration

**Files:**

- Modify: `app/models/__init__.py`
- Create: `app/models/agents.py`
- Create: `migrations/versions/20260526_0002_create_agents.py`
- Test: `tests/test_agent_models.py`

**Step 1: Write failing model tests**

Add to `tests/test_agent_models.py`:

```python
from app.models.agents import Agent, AgentVersion


def test_agent_table_name() -> None:
    assert Agent.__tablename__ == "agents"


def test_agent_version_table_name() -> None:
    assert AgentVersion.__tablename__ == "agent_versions"
```

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_agent_models.py -v
```

Expected: import failure for `app.models.agents`.

**Step 3: Implement ORM models**

Create `app/models/agents.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (Index("uq_agents_key", "key", unique=True),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    draft_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latest_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_versions.id", use_alter=True),
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        foreign_keys="AgentVersion.agent_id",
    )
    latest_version: Mapped["AgentVersion | None"] = relationship(
        foreign_keys=[latest_version_id],
        post_update=True,
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        Index(
            "uq_agent_versions_agent_version",
            "agent_id",
            "version_number",
            unique=True,
        ),
        Index("ix_agent_versions_agent_published", "agent_id", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    tool_allowlist: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    mcp_server_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    published_by: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    agent: Mapped[Agent] = relationship(
        back_populates="versions",
        foreign_keys=[agent_id],
    )
```

Modify `app/models/__init__.py` only if existing tests or Alembic need explicit
imports. Prefer matching the current project pattern.

**Step 4: Add Alembic migration**

Create `migrations/versions/20260526_0002_create_agents.py` with:

```python
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260526_0002"
down_revision = "20260525_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("draft_config", postgresql.JSONB(), nullable=True),
        sa.Column("latest_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "agent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("model_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("tool_allowlist", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("mcp_server_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("published_by", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
    )
    op.create_index("uq_agents_key", "agents", ["key"], unique=True)
    op.create_index(
        "uq_agent_versions_agent_version",
        "agent_versions",
        ["agent_id", "version_number"],
        unique=True,
    )
    op.create_index(
        "ix_agent_versions_agent_published",
        "agent_versions",
        ["agent_id", "published_at"],
    )
    op.create_foreign_key(
        "fk_agents_latest_version_id",
        "agents",
        "agent_versions",
        ["latest_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_agents_latest_version_id", "agents", type_="foreignkey")
    op.drop_index("ix_agent_versions_agent_published", table_name="agent_versions")
    op.drop_index("uq_agent_versions_agent_version", table_name="agent_versions")
    op.drop_index("uq_agents_key", table_name="agents")
    op.drop_table("agent_versions")
    op.drop_table("agents")
```

Remove unused imports after creating the file.

**Step 5: Verify**

Run:

```bash
uv run pytest tests/test_agent_models.py -v
uv run pytest tests/test_models.py -v
```

Expected: pass.

If `TEST_DATABASE_URL` is configured, also run:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent_test uv run pytest tests/test_run_repository.py -v
```

Expected: existing DB tests still pass.

**Step 6: Commit**

```bash
git add app/models app/models/__init__.py migrations/versions/20260526_0002_create_agents.py tests/test_agent_models.py
git commit -m "feat: add agent persistence models"
```

---

### Task 3: Add Agent Repository

**Files:**

- Create: `app/repositories/agents.py`
- Modify: `app/repositories/__init__.py`
- Test: `tests/test_agent_repository.py`

**Step 1: Write repository tests**

Create tests with fake DB session only if possible. Prefer DB-backed tests if
the project has the same pattern available for `RunRepository`.

Minimum DB-backed cases:

```python
import pytest

from app.repositories.agents import AgentKeyExistsError, AgentRepository
from app.schemas.agents import AgentDraftConfig


@pytest.mark.db
async def test_create_agent_stores_draft(db_session) -> None:
    repository = AgentRepository(db_session)

    agent = await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        description=None,
        draft=AgentDraftConfig(
            system_prompt="You are careful.",
            model="openai:gpt-5-mini",
        ),
    )

    assert agent.key == "release-reviewer"
    assert agent.draft_config["model"] == "openai:gpt-5-mini"


@pytest.mark.db
async def test_publish_agent_creates_monotonic_versions(db_session) -> None:
    repository = AgentRepository(db_session)
    await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        description=None,
        draft=AgentDraftConfig(
            system_prompt="Prompt v1",
            model="openai:gpt-5-mini",
        ),
    )

    first = await repository.publish_agent("release-reviewer")
    second = await repository.publish_agent("release-reviewer")

    assert first.version_number == 1
    assert second.version_number == 2
```

If existing project fixtures do not expose `db_session`, first inspect
`tests/test_run_repository.py` and follow that fixture style.

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_agent_repository.py -v
```

Expected: import or fixture failure. If DB is unavailable, skipped DB tests are
acceptable when marked consistently with existing DB tests.

**Step 3: Implement repository**

Create `app/repositories/agents.py`:

```python
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agents import Agent, AgentVersion
from app.schemas.agents import AgentDraftConfig


class AgentKeyExistsError(Exception):
    pass


class AgentNotFoundError(Exception):
    pass


class AgentDraftInvalidError(Exception):
    pass


class AgentVersionNotFoundError(Exception):
    pass


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_agent(
        self,
        *,
        key: str,
        display_name: str,
        description: str | None,
        draft: AgentDraftConfig,
        created_by: str | None = None,
    ) -> Agent:
        agent = Agent(
            key=key,
            display_name=display_name,
            description=description,
            draft_config=draft.model_dump(mode="json"),
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(agent)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise AgentKeyExistsError(key) from exc
        return agent

    async def list_agents(self, *, include_deleted: bool = False) -> list[Agent]:
        statement = (
            select(Agent)
            .options(selectinload(Agent.latest_version))
            .order_by(Agent.created_at.desc())
        )
        if not include_deleted:
            statement = statement.where(Agent.deleted_at.is_(None))
        return list((await self._session.scalars(statement)).all())

    async def get_agent(self, key: str, *, include_deleted: bool = False) -> Agent | None:
        statement = (
            select(Agent)
            .where(Agent.key == key)
            .options(selectinload(Agent.latest_version))
            .limit(1)
        )
        if not include_deleted:
            statement = statement.where(Agent.deleted_at.is_(None))
        return await self._session.scalar(statement)

    async def update_draft(
        self,
        key: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        draft: AgentDraftConfig | None = None,
        updated_by: str | None = None,
    ) -> Agent:
        agent = await self._require_agent(key)
        if display_name is not None:
            agent.display_name = display_name
        if description is not None:
            agent.description = description
        if enabled is not None:
            agent.enabled = enabled
        if draft is not None:
            agent.draft_config = draft.model_dump(mode="json")
        agent.updated_by = updated_by
        await self._session.flush()
        return agent

    async def publish_agent(
        self,
        key: str,
        *,
        published_by: str | None = None,
    ) -> AgentVersion:
        agent = await self._lock_agent(key)
        if not agent.draft_config:
            raise AgentDraftInvalidError(key)

        draft = AgentDraftConfig.model_validate(agent.draft_config)
        next_version = await self._next_version_number(agent.id)
        version = AgentVersion(
            agent_id=agent.id,
            version_number=next_version,
            system_prompt=draft.system_prompt,
            model=draft.model,
            model_config=draft.model_config,
            tool_allowlist=draft.tool_allowlist,
            mcp_server_ids=draft.mcp_server_ids,
            published_by=published_by,
            published_at=datetime.now(UTC),
        )
        self._session.add(version)
        await self._session.flush()
        agent.latest_version_id = version.id
        agent.updated_by = published_by
        await self._session.flush()
        return version

    async def list_versions(self, key: str) -> list[AgentVersion]:
        agent = await self._require_agent(key)
        statement = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent.id)
            .order_by(AgentVersion.version_number.desc())
        )
        return list((await self._session.scalars(statement)).all())

    async def get_version_by_number(
        self,
        key: str,
        version_number: int,
    ) -> AgentVersion | None:
        agent = await self._require_agent(key)
        statement = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent.id)
            .where(AgentVersion.version_number == version_number)
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def get_version_by_id(self, version_id: UUID) -> AgentVersion | None:
        return await self._session.get(AgentVersion, version_id)

    async def soft_delete(self, key: str, *, updated_by: str | None = None) -> Agent:
        agent = await self._require_agent(key)
        agent.deleted_at = datetime.now(UTC)
        agent.updated_by = updated_by
        await self._session.flush()
        return agent

    async def _require_agent(self, key: str) -> Agent:
        agent = await self.get_agent(key)
        if agent is None:
            raise AgentNotFoundError(key)
        return agent

    async def _lock_agent(self, key: str) -> Agent:
        statement = (
            select(Agent)
            .where(Agent.key == key)
            .where(Agent.deleted_at.is_(None))
            .with_for_update()
            .limit(1)
        )
        agent = await self._session.scalar(statement)
        if agent is None:
            raise AgentNotFoundError(key)
        return agent

    async def _next_version_number(self, agent_id: UUID) -> int:
        statement = select(func.coalesce(func.max(AgentVersion.version_number), 0)).where(
            AgentVersion.agent_id == agent_id
        )
        latest = await self._session.scalar(statement)
        return int(latest or 0) + 1
```

Remove unused imports after implementation. Handle `description=None` carefully:
if the API needs to distinguish "omitted" from "set null", adjust
`AgentDraftUpdate` or service logic in a later task.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/test_agent_repository.py -v
```

Expected: pass or skip DB tests when DB is unavailable.

**Step 5: Commit**

```bash
git add app/repositories/agents.py app/repositories/__init__.py tests/test_agent_repository.py
git commit -m "feat: add agent repository"
```

---

### Task 4: Add Agent Service for CRUD and Publishing

**Files:**

- Create: `app/services/agents.py`
- Test: `tests/test_agent_service.py`

**Step 1: Write failing service tests with fakes**

Create `tests/test_agent_service.py`:

```python
from uuid import uuid4

import pytest

from app.schemas.agents import AgentCreate, AgentDraftConfig
from app.services.agents import AgentService


class FakeAgentRepository:
    def __init__(self) -> None:
        self.created = None
        self.published = False

    async def create_agent(self, **kwargs):
        self.created = kwargs
        return type(
            "Agent",
            (),
            {
                "id": uuid4(),
                "key": kwargs["key"],
                "display_name": kwargs["display_name"],
                "description": kwargs["description"],
                "enabled": True,
                "draft_config": kwargs["draft"].model_dump(mode="json"),
                "latest_version": None,
                "created_at": None,
                "updated_at": None,
            },
        )()

    async def publish_agent(self, key, **kwargs):
        self.published = True
        return type(
            "Version",
            (),
            {
                "id": uuid4(),
                "agent_id": uuid4(),
                "version_number": 1,
                "system_prompt": "Prompt",
                "model": "openai:gpt-5-mini",
                "model_config": {},
                "tool_allowlist": [],
                "mcp_server_ids": [],
                "published_by": None,
                "published_at": None,
            },
        )()


@pytest.mark.asyncio
async def test_create_agent_delegates_to_repository() -> None:
    repository = FakeAgentRepository()
    service = AgentService(repository=repository, commit=lambda: None)

    await service.create_agent(
        AgentCreate(
            key="release-reviewer",
            display_name="Release Reviewer",
            description=None,
            draft=AgentDraftConfig(
                system_prompt="Prompt",
                model="openai:gpt-5-mini",
            ),
        )
    )

    assert repository.created["key"] == "release-reviewer"
```

Adapt fake timestamps if response schema requires non-null datetimes. It is OK
to test service behavior rather than response serialization here.

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_agent_service.py -v
```

Expected: import failure for `app.services.agents`.

**Step 3: Implement service**

Create `app/services/agents.py`:

```python
import inspect
from collections.abc import Awaitable, Callable

from app.repositories.agents import AgentRepository
from app.schemas.agents import AgentCreate, AgentDraftUpdate


Committer = Callable[[], Awaitable[None] | None]


async def _noop_commit() -> None:
    return None


class AgentService:
    def __init__(
        self,
        *,
        repository: AgentRepository,
        commit: Committer = _noop_commit,
    ) -> None:
        self._repository = repository
        self._commit = commit

    async def create_agent(self, request: AgentCreate):
        agent = await self._repository.create_agent(
            key=request.key,
            display_name=request.display_name,
            description=request.description,
            draft=request.draft,
        )
        await self._commit_if_configured()
        return agent

    async def update_draft(self, agent_key: str, request: AgentDraftUpdate):
        agent = await self._repository.update_draft(
            agent_key,
            display_name=request.display_name,
            description=request.description,
            enabled=request.enabled,
            draft=request.draft,
        )
        await self._commit_if_configured()
        return agent

    async def publish_agent(self, agent_key: str):
        version = await self._repository.publish_agent(agent_key)
        await self._commit_if_configured()
        return version

    async def delete_agent(self, agent_key: str):
        agent = await self._repository.soft_delete(agent_key)
        await self._commit_if_configured()
        return agent

    async def _commit_if_configured(self) -> None:
        result = self._commit()
        if inspect.isawaitable(result):
            await result
```

This service will grow in the test-run task. Keep it thin for CRUD and
publishing.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/test_agent_service.py -v
```

Expected: pass.

**Step 5: Commit**

```bash
git add app/services/agents.py tests/test_agent_service.py
git commit -m "feat: add agent service"
```

---

### Task 5: Add FastAPI Dependencies and CRUD Routes

**Files:**

- Modify: `app/api/deps.py`
- Create: `app/api/v1/agents.py`
- Modify: `app/main.py`
- Test: `tests/test_agents_api.py`

**Step 1: Write failing API tests**

Create `tests/test_agents_api.py` using the same `ASGITransport` pattern as
`tests/test_sop_api.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_agent_repository, get_session
from app.main import app


class FakeSession:
    async def commit(self) -> None:
        return None


class FakeAgentRepository:
    def __init__(self) -> None:
        self.agent_id = uuid4()

    async def create_agent(self, **kwargs):
        return self._agent(kwargs["key"], kwargs["display_name"], kwargs["draft"])

    async def get_agent(self, key, **kwargs):
        return self._agent(key, "Release Reviewer", None)

    async def list_agents(self, **kwargs):
        return [self._agent("release-reviewer", "Release Reviewer", None)]

    async def publish_agent(self, key, **kwargs):
        return self._version()

    async def soft_delete(self, key, **kwargs):
        agent = self._agent(key, "Release Reviewer", None)
        agent.deleted_at = datetime.now(UTC)
        return agent

    def _agent(self, key, display_name, draft):
        return type(
            "Agent",
            (),
            {
                "id": self.agent_id,
                "key": key,
                "display_name": display_name,
                "description": None,
                "enabled": True,
                "draft_config": draft.model_dump(mode="json") if draft else None,
                "latest_version": None,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )()

    def _version(self):
        return type(
            "Version",
            (),
            {
                "id": uuid4(),
                "agent_id": self.agent_id,
                "version_number": 1,
                "system_prompt": "Prompt",
                "model": "openai:gpt-5-mini",
                "model_config": {},
                "tool_allowlist": [],
                "mcp_server_ids": [],
                "published_by": None,
                "published_at": datetime.now(UTC),
            },
        )()


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_session_override():
    async def override_session():
        yield FakeSession()

    return override_session


@pytest.mark.asyncio
async def test_create_agent_returns_created() -> None:
    app.dependency_overrides[get_session] = make_session_override()
    app.dependency_overrides[get_agent_repository] = lambda: FakeAgentRepository()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/agents",
            json={
                "key": "release-reviewer",
                "display_name": "Release Reviewer",
                "draft": {
                    "system_prompt": "Prompt",
                    "model": "openai:gpt-5-mini",
                },
            },
        )

    assert response.status_code == 201
    assert response.json()["key"] == "release-reviewer"
```

Add tests for list, get, publish, and delete after the first route works.

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_agents_api.py -v
```

Expected: import failure for `get_agent_repository` or 404 for `/api/agents`.

**Step 3: Add dependency**

Modify `app/api/deps.py`:

```python
from app.repositories.agents import AgentRepository


def get_agent_repository(session: SessionDep) -> AgentRepository:
    return AgentRepository(session)


AgentRepositoryDep = Annotated[AgentRepository, Depends(get_agent_repository)]
```

Keep the existing SOP and run dependencies unchanged.

**Step 4: Add route helpers**

Create `app/api/v1/agents.py` with mapping helpers:

```python
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import AgentRepositoryDep, SessionDep
from app.repositories.agents import (
    AgentDraftInvalidError,
    AgentKeyExistsError,
    AgentNotFoundError,
)
from app.schemas.agents import (
    AgentCreate,
    AgentDetail,
    AgentDraftConfig,
    AgentDraftUpdate,
    AgentSummary,
    AgentVersionDetail,
)
from app.services.agents import AgentService

router = APIRouter(prefix="/api/agents", tags=["agents"])
```

Add helpers:

```python
def agent_to_detail(agent) -> AgentDetail:
    return AgentDetail(
        id=agent.id,
        key=agent.key,
        display_name=agent.display_name,
        description=agent.description,
        enabled=agent.enabled,
        has_draft=agent.draft_config is not None,
        latest_version=agent.latest_version,
        draft=(
            AgentDraftConfig.model_validate(agent.draft_config)
            if agent.draft_config
            else None
        ),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def agent_to_summary(agent) -> AgentSummary:
    return AgentSummary(
        id=agent.id,
        key=agent.key,
        display_name=agent.display_name,
        description=agent.description,
        enabled=agent.enabled,
        has_draft=agent.draft_config is not None,
        latest_version=agent.latest_version,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def version_to_detail(version) -> AgentVersionDetail:
    return AgentVersionDetail.model_validate(version)
```

**Step 5: Add CRUD endpoints**

Implement:

```python
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        agent = await service.create_agent(request)
    except AgentKeyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT) from exc
    return agent_to_detail(agent)


@router.get("")
async def list_agents(
    repository: AgentRepositoryDep,
    include_deleted: Annotated[bool, Query()] = False,
) -> list[AgentSummary]:
    agents = await repository.list_agents(include_deleted=include_deleted)
    return [agent_to_summary(agent) for agent in agents]


@router.get("/{agent_key}")
async def get_agent(agent_key: str, repository: AgentRepositoryDep) -> AgentDetail:
    agent = await repository.get_agent(agent_key)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return agent_to_detail(agent)


@router.patch("/{agent_key}/draft")
async def update_agent_draft(
    agent_key: str,
    request: AgentDraftUpdate,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        agent = await service.update_draft(agent_key, request)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return agent_to_detail(agent)


@router.post("/{agent_key}/publish", status_code=status.HTTP_201_CREATED)
async def publish_agent(
    agent_key: str,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentVersionDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        version = await service.publish_agent(agent_key)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except AgentDraftInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc
    return version_to_detail(version)


@router.delete("/{agent_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_key: str,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> Response:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        await service.delete_agent(agent_key)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Add version list/get routes after repository methods are tested.

**Step 6: Register router**

Modify `app/main.py`:

```python
from app.api.v1 import agents, runs, sop

app.include_router(agents.router)
```

Keep existing routers.

**Step 7: Verify**

Run:

```bash
uv run pytest tests/test_agents_api.py -v
uv run pytest tests/test_sop_api.py tests/test_runs_api.py -v
```

Expected: pass.

**Step 8: Commit**

```bash
git add app/api/deps.py app/api/v1/agents.py app/main.py tests/test_agents_api.py
git commit -m "feat: add agent CRUD API"
```

---

### Task 6: Add Agent Test Run Creation

**Files:**

- Modify: `app/repositories/runs.py`
- Modify: `app/services/agents.py`
- Modify: `app/api/v1/agents.py`
- Test: `tests/test_agent_test_runs.py`

**Step 1: Write failing service/API tests**

Create `tests/test_agent_test_runs.py` with service-level fakes first:

```python
from uuid import uuid4

import pytest

from app.schemas.agents import AgentTestRunCreate
from app.services.agents import AgentService


class FakeAgentRepository:
    async def get_agent(self, key):
        return type(
            "Agent",
            (),
            {
                "id": uuid4(),
                "key": key,
                "enabled": True,
                "deleted_at": None,
                "latest_version_id": uuid4(),
                "latest_version": self._version(2),
            },
        )()

    async def get_version_by_number(self, key, version_number):
        return self._version(version_number)

    async def get_version_by_id(self, version_id):
        return self._version(1)

    def _version(self, version_number):
        return type(
            "Version",
            (),
            {
                "id": uuid4(),
                "agent_id": uuid4(),
                "version_number": version_number,
                "system_prompt": "Prompt",
                "model": "openai:gpt-5-mini",
                "model_config": {},
                "tool_allowlist": [],
                "mcp_server_ids": [],
            },
        )()


class FakeRunRepository:
    async def create_agent_test_run(self, **kwargs):
        return type(
            "Run",
            (),
            {
                "id": uuid4(),
                "status": "pending",
            },
        )()


@pytest.mark.asyncio
async def test_start_test_run_defaults_to_latest_version() -> None:
    scheduled = []
    service = AgentService(
        repository=FakeAgentRepository(),
        run_repository=FakeRunRepository(),
        schedule_run=scheduled.append,
        commit=lambda: None,
    )

    result = await service.start_test_run(
        "release-reviewer",
        AgentTestRunCreate(
            messages=[{"role": "user", "content": "Review this."}]
        ),
    )

    assert result.status_url == f"/api/runs/{result.run_id}"
    assert scheduled == [result.run_id]
```

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_agent_test_runs.py -v
```

Expected: `AgentService` does not accept `run_repository` or lacks
`start_test_run`.

**Step 3: Extend `RunRepository`**

Modify `app/repositories/runs.py` with `create_agent_test_run`:

```python
async def create_agent_test_run(
    self,
    *,
    agent_key: str,
    agent_id: str,
    agent_version_id: str,
    agent_version_number: int,
    messages: list[dict[str, str]],
    input_preview: str,
    created_by: str | None = None,
    assistant_id: str = "react-agent-test-v1",
) -> Run:
    run = Run(
        thread_id=str(uuid4()),
        assistant_id=assistant_id,
        subject_type="agent_test",
        subject_id=agent_key,
        env_key=None,
        status=RunStatus.pending.value,
        active_conflict_key=None,
        metadata_={
            "subject_type": "agent_test",
            "subject_id": agent_key,
            "agent_id": str(agent_id),
            "agent_key": agent_key,
            "agent_version_id": str(agent_version_id),
            "agent_version_number": agent_version_number,
            "run_kind": "agent_test",
            "input_preview": input_preview,
        },
        kwargs={
            "agent_key": agent_key,
            "agent_version_id": str(agent_version_id),
            "agent_version_number": agent_version_number,
        },
        completed_nodes=[],
        subject_snapshot={
            "messages": messages,
            "agent_version": {
                "id": str(agent_version_id),
                "version_number": agent_version_number,
            },
        },
        created_by=created_by,
    )
    self._session.add(run)
    await self._session.flush()
    return run
```

Import or reuse `uuid4` already present in `runs.py`.

**Step 4: Extend service**

Modify `app/services/agents.py`:

- Add `RunStartResult` reuse or import from `app.services.sop_quality` if it is
  appropriate. Prefer moving it only if needed; avoid broad refactors.
- Add `run_repository` and `schedule_run`.
- Add `start_test_run`.

Sketch:

```python
from app.schemas.agents import AgentTestRunCreate
from app.schemas.runs import RunStatus
from app.services.sop_quality import RunStartResult


async def start_test_run(
    self,
    agent_key: str,
    request: AgentTestRunCreate,
) -> RunStartResult:
    agent = await self._repository.get_agent(agent_key)
    if agent is None or not agent.enabled:
        raise AgentNotFoundError(agent_key)

    version = await self._resolve_version(agent_key, agent, request)
    messages = [message.model_dump(mode="json") for message in request.messages]
    run = await self._run_repository.create_agent_test_run(
        agent_key=agent.key,
        agent_id=agent.id,
        agent_version_id=version.id,
        agent_version_number=version.version_number,
        messages=messages,
        input_preview=_preview_messages(messages),
    )
    await self._commit_if_configured()
    await self._schedule_if_configured(run.id)
    return RunStartResult(
        accepted=True,
        run_id=run.id,
        status=RunStatus.pending,
        status_url=f"/api/runs/{run.id}",
        events_url=f"/api/runs/{run.id}/events",
    )
```

Add `_preview_messages`:

```python
def _preview_messages(messages: list[dict[str, str]]) -> str:
    first_user = next(
        (message["content"] for message in messages if message["role"] == "user"),
        "",
    )
    return first_user[:200]
```

**Step 5: Add route**

In `app/api/v1/agents.py`, add:

```python
@router.post("/{agent_key}/test-runs")
async def start_agent_test_run(
    agent_key: str,
    request: AgentTestRunCreate,
    background_tasks: BackgroundTasks,
    fastapi_request: Request,
    session: SessionDep,
    agent_repository: AgentRepositoryDep,
    run_repository: RunRepositoryDep,
) -> RunStartResponse:
    def schedule_run(run_id):
        executor = getattr(
            fastapi_request.app.state,
            "agent_test_run_executor",
            run_agent_test_with_new_session,
        )
        background_tasks.add_task(executor, run_id)

    service = AgentService(
        repository=agent_repository,
        run_repository=run_repository,
        schedule_run=schedule_run,
        commit=session.commit,
    )
    try:
        result = await service.start_test_run(agent_key, request)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except AgentVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=RunStartResponse(
            run_id=result.run_id,
            status=result.status,
            status_url=result.status_url,
            events_url=result.events_url,
        ).model_dump(mode="json"),
    )
```

Import `BackgroundTasks`, `Request`, `JSONResponse`, `RunRepositoryDep`,
`RunStartResponse`, and executor placeholder. The executor is implemented in
the runtime task; until then, define a stub that marks an error or use an import
that will fail in the next task's tests.

**Step 6: Verify**

Run:

```bash
uv run pytest tests/test_agent_test_runs.py tests/test_agents_api.py -v
```

Expected: pass after executor placeholder is handled.

**Step 7: Commit**

```bash
git add app/repositories/runs.py app/services/agents.py app/api/v1/agents.py tests/test_agent_test_runs.py
git commit -m "feat: start agent test runs"
```

---

### Task 7: Add LangChain Runtime Adapter and Executor

**Files:**

- Create: `agent/react_runtime.py`
- Modify: `app/services/agents.py`
- Test: `tests/test_agent_runtime.py`
- Test: `tests/test_agent_test_run_executor.py`

**Step 1: Write runtime tests**

Create `tests/test_agent_runtime.py`:

```python
import pytest

from agent.react_runtime import AgentRuntime, StaticToolResolver


class FakeCreateAgent:
    def __call__(self, *, model, tools, system_prompt):
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        return self

    async def ainvoke(self, payload):
        self.payload = payload
        return {"messages": [{"role": "assistant", "content": "Looks good."}]}


@pytest.mark.asyncio
async def test_runtime_passes_version_to_create_agent() -> None:
    factory = FakeCreateAgent()
    version = type(
        "Version",
        (),
        {
            "system_prompt": "Prompt",
            "model": "openai:gpt-5-mini",
            "tool_allowlist": [],
            "mcp_server_ids": [],
        },
    )()
    runtime = AgentRuntime(
        create_agent=factory,
        tool_resolver=StaticToolResolver(),
    )

    result = await runtime.run(
        version=version,
        messages=[{"role": "user", "content": "Review."}],
    )

    assert factory.model == "openai:gpt-5-mini"
    assert factory.system_prompt == "Prompt"
    assert result.messages[0]["content"] == "Looks good."
```

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_agent_runtime.py -v
```

Expected: import failure.

**Step 3: Implement runtime**

Create `agent/react_runtime.py`:

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent as langchain_create_agent


@dataclass(frozen=True)
class AgentRunResult:
    messages: list[dict[str, Any]]
    raw_output: dict[str, Any]


class StaticToolResolver:
    async def resolve(
        self,
        *,
        tool_allowlist: list[str],
        mcp_server_ids: list[str],
    ) -> list[Any]:
        return []


class AgentRuntime:
    def __init__(
        self,
        *,
        create_agent: Callable[..., Any] = langchain_create_agent,
        tool_resolver: StaticToolResolver | None = None,
    ) -> None:
        self._create_agent = create_agent
        self._tool_resolver = tool_resolver or StaticToolResolver()

    async def run(
        self,
        *,
        version,
        messages: list[dict[str, str]],
    ) -> AgentRunResult:
        tools = await self._tool_resolver.resolve(
            tool_allowlist=list(version.tool_allowlist),
            mcp_server_ids=list(version.mcp_server_ids),
        )
        agent = self._create_agent(
            model=version.model,
            tools=tools,
            system_prompt=version.system_prompt,
        )
        raw_output = await agent.ainvoke({"messages": messages})
        return AgentRunResult(
            messages=_extract_messages(raw_output),
            raw_output=raw_output,
        )


def _extract_messages(raw_output: dict[str, Any]) -> list[dict[str, Any]]:
    messages = raw_output.get("messages", [])
    return [
        message if isinstance(message, dict) else {"content": str(message)}
        for message in messages
    ]
```

If the installed LangChain API uses `prompt` instead of `system_prompt`, adjust
the adapter here only. Do not leak that difference into API schemas.

**Step 4: Implement executor**

In `app/services/agents.py` or a new `app/services/agent_tests.py`, add
`run_agent_test` and `run_agent_test_with_new_session`.

Prefer a new service file if `app/services/agents.py` grows too large.

Executor sketch:

```python
from app.core.database import async_session
from app.repositories.agents import AgentRepository
from app.repositories.runs import RunRepository
from app.schemas.runs import RunStatus
from agent.react_runtime import AgentRuntime


async def run_agent_test(run_id, run_repository, agent_repository, runtime=None):
    runtime = runtime or AgentRuntime()
    run = await run_repository.mark_running(run_id)
    version_id = run.metadata_["agent_version_id"]
    version = await agent_repository.get_version_by_id(version_id)
    if version is None:
        raise AgentVersionNotFoundError(version_id)

    await run_repository.append_event(
        run_id,
        event_type="custom",
        thread_id=run.thread_id,
        payload={
            "message": "Started ReAct agent test run.",
            "agent_key": run.metadata_["agent_key"],
            "agent_version_number": run.metadata_["agent_version_number"],
        },
        node="react_agent",
    )
    try:
        result = await runtime.run(
            version=version,
            messages=run.subject_snapshot["messages"],
        )
        await run_repository.append_event(
            run_id,
            event_type="messages",
            thread_id=run.thread_id,
            payload={"messages": result.messages},
            node="react_agent",
        )
        await run_repository.append_event(
            run_id,
            event_type="done",
            thread_id=run.thread_id,
            payload={"status": "done", "result_status": "success"},
        )
        await run_repository.mark_terminal(
            run_id,
            RunStatus.success,
            structured_result={"messages": result.messages},
            raw_graph_output=result.raw_output,
            result_status="success",
        )
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        await run_repository.append_event(
            run_id,
            event_type="error",
            thread_id=run.thread_id,
            payload=error,
            node="react_agent",
        )
        await run_repository.mark_terminal(
            run_id,
            RunStatus.error,
            error=error,
            result_status="error",
        )
    await run_repository.commit()


async def run_agent_test_with_new_session(run_id):
    async with async_session() as session:
        run_repository = RunRepository(session)
        agent_repository = AgentRepository(session)
        return await run_agent_test(run_id, run_repository, agent_repository)
```

Be careful: if `get_version_by_id` expects a UUID, convert the metadata string
back to `UUID`.

**Step 5: Write executor tests**

Use fake repositories and fake runtime:

```python
@pytest.mark.asyncio
async def test_agent_test_executor_marks_success() -> None:
    # Fake run repository captures append_event and mark_terminal calls.
    # Fake agent repository returns a version.
    # Fake runtime returns AgentRunResult(messages=[...], raw_output={...}).
    ...
```

Assert:

- `custom`, `messages`, and `done` events are appended.
- terminal status is `RunStatus.success`.

Add failure test:

- fake runtime raises `RuntimeError("model failed")`.
- an `error` event is appended.
- terminal status is `RunStatus.error`.

**Step 6: Verify**

Run:

```bash
uv run pytest tests/test_agent_runtime.py tests/test_agent_test_run_executor.py tests/test_agent_test_runs.py -v
```

Expected: pass.

**Step 7: Commit**

```bash
git add agent/react_runtime.py app/services/agents.py tests/test_agent_runtime.py tests/test_agent_test_run_executor.py
git commit -m "feat: run react agent tests"
```

---

### Task 8: Update OpenAPI Contract

**Files:**

- Modify: `api/openapi.yml`
- Test: `tests/test_openapi_contract.py` or existing contract test if present

**Step 1: Add a failing contract smoke test**

If no OpenAPI test exists, create `tests/test_openapi_contract.py`:

```python
from pathlib import Path

import yaml


def test_agents_paths_are_documented() -> None:
    contract = yaml.safe_load(Path("api/openapi.yml").read_text())

    assert "/api/agents" in contract["paths"]
    assert "/api/agents/{agent_key}/publish" in contract["paths"]
    assert "/api/agents/{agent_key}/test-runs" in contract["paths"]
    assert "AgentDraftConfig" in contract["components"]["schemas"]
```

**Step 2: Verify failure**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -v
```

Expected: missing path assertions fail.

**Step 3: Update `api/openapi.yml`**

Add tag:

```yaml
- name: agents
  description: ReAct agent definitions, versions, and test runs.
```

Add paths:

- `/api/agents`
- `/api/agents/{agent_key}`
- `/api/agents/{agent_key}/draft`
- `/api/agents/{agent_key}/publish`
- `/api/agents/{agent_key}/versions`
- `/api/agents/{agent_key}/versions/{version_number}`
- `/api/agents/{agent_key}/test-runs`

Add schemas:

- `AgentDraftConfig`
- `AgentCreate`
- `AgentDraftUpdate`
- `AgentSummary`
- `AgentDetail`
- `AgentVersionSummary`
- `AgentVersionDetail`
- `AgentMessage`
- `AgentTestRunCreate`

Reuse existing `RunStartResponse`, `ErrorResponse`, and
`ValidationErrorResponse`.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -v
```

Expected: pass.

**Step 5: Commit**

```bash
git add api/openapi.yml tests/test_openapi_contract.py
git commit -m "docs: document agent API contract"
```

---

### Task 9: Full Verification and Cleanup

**Files:**

- Modify only files required by failing checks.

**Step 1: Run focused tests**

```bash
uv run pytest \
  tests/test_agent_schemas.py \
  tests/test_agent_models.py \
  tests/test_agent_repository.py \
  tests/test_agent_service.py \
  tests/test_agents_api.py \
  tests/test_agent_test_runs.py \
  tests/test_agent_runtime.py \
  tests/test_agent_test_run_executor.py \
  tests/test_openapi_contract.py \
  -v
```

Expected: all pass, except DB tests may skip if no test database is configured.

**Step 2: Run full suite**

```bash
uv run pytest
```

Expected: existing and new tests pass.

**Step 3: Check formatting and whitespace**

```bash
git diff --check
```

Expected: no output.

**Step 4: Inspect final diff**

```bash
git status --short
git diff --stat
```

Expected: only intended files changed.

**Step 5: Final commit if needed**

If verification fixes were required:

```bash
git add <fixed-files>
git commit -m "test: verify agent CRUD flow"
```

If no files changed, do not create an empty commit.

---

## Implementation Notes

- Do not modify the main worktree. Stay in
  `/Users/wanyaozhong/Projects/change-quality-agent/.worktrees/react-agent-crud-design`.
- Do not commit `.agents/` or `skills-lock.json`.
- Keep every Python file under 1000 lines.
- Prefer extending existing generic run helpers over duplicating run status or
  SSE behavior.
- Keep tool and MCP behavior behind resolver interfaces. Do not build those
  modules here.
- Keep LLM provider semantics out of this feature. Store only the model string
  and JSON config.
- If LangChain's current `create_agent` signature differs from the plan, adapt
  only inside `agent/react_runtime.py`.

## Execution Handoff

Plan complete and saved to
`docs/plans/2026-05-26-react-agent-crud-implementation.md`.

Two execution options:

1. **Subagent-Driven (this session)** - Dispatch a fresh subagent per task,
   review between tasks, and iterate quickly.
2. **Parallel Session (separate)** - Open a new session in this worktree with
   `superpowers:executing-plans`, then execute with checkpoints.

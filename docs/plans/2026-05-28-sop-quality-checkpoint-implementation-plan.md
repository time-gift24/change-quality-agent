# SOP Quality Checkpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the generic `runs/run_events` SOP quality execution path with a dedicated SOP quality check flow backed by LangGraph Postgres checkpoints, while preserving history and letting multiple users join the same active SOP/env check.

**Architecture:** `sop_quality_checks` stores business lifecycle/history and latest checkpoint pointers, `sop_quality_events` stores lightweight SSE cursors only, and LangGraph checkpoint tables store graph state/messages/resume data. The FastAPI layer exposes `/api/sop-quality-checks/*`, the runner executes one code-defined SOP quality LangGraph graph, and the React UI observes checks by `checkId` instead of generic `runId`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async ORM, Alembic, Postgres 13 partial unique indexes, LangGraph `StateGraph`, `langgraph-checkpoint-postgres` `AsyncPostgresSaver`, React 19, Vite, TypeScript, Tailwind CSS v4, Vitest.

---

## Execution Notes

- Use @superpowers:using-git-worktrees before implementation. Execute from a clean implementation worktree based on the design commit, not from the existing dirty experiment unless the user explicitly asks to salvage it.
- Use @superpowers:test-driven-development for every behavior change.
- Use @fastapi and @project-structure for backend/API changes.
- Read root `DESIGN.md` before frontend changes and keep the existing SOP chat UI visual language.
- Stage and commit only the files listed in each task. Do not commit `.agents/`, `skills-lock.json`, `.venv/`, `__pycache__/`, or old experimental scratch files.
- The current design reference is `docs/plans/2026-05-28-sop-quality-checkpoint-design.md`.

## Target API Decisions

- New create/join endpoint: `POST /api/sop-quality-checks?sop_id=<sop_id>&env=<env_key>`.
- New checks get HTTP `202` with `created: true`.
- Existing active checks get HTTP `200` with `created: false`.
- There is no `409` for same SOP/env active checks; joining is the product behavior.
- Stream events do not persist token payloads. Durable event replay only carries `sequence`, `type`, `node`, `checkpoint_id`, `task_id`, `message`, and timestamps.

---

### Task 1: Clean Implementation Baseline

**Files:**
- Read: `AGENTS.md`
- Read: `docs/plans/2026-05-28-sop-quality-checkpoint-design.md`
- Modify: none

**Step 1: Create or enter a clean worktree**

Run from the main repository path:

```bash
git worktree add .worktrees/sop-quality-checkpoint-impl -b codex/sop-quality-checkpoint-impl 693c8b4
cd .worktrees/sop-quality-checkpoint-impl
```

Expected: new worktree on `codex/sop-quality-checkpoint-impl`.

**Step 2: Verify baseline status**

Run:

```bash
git status --short
```

Expected: no output.

**Step 3: Run focused baseline tests**

Run:

```bash
uv run pytest tests/test_sop_api.py tests/test_sop_quality_service.py tests/test_runs_api.py -q
```

Expected: current baseline passes before deletion. If it fails, stop and inspect; do not continue from a broken baseline.

**Step 4: Confirm frontend baseline**

Run:

```bash
cd frontend
npm run test -- --run frontend/src/features/sop/api.test.ts frontend/src/features/runs/hooks.test.tsx
```

Expected: current baseline passes.

**Step 5: Commit**

No commit for this task.

---

### Task 2: SOP Quality Models And Base Migration

**Files:**
- Create: `app/models/sop_quality_checks.py`
- Modify: `app/models/__init__.py`
- Rename: `migrations/versions/20260525_0001_create_runs.py` -> `migrations/versions/20260525_0001_create_sop_quality_checks.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_migrations.py`

**Step 1: Write failing model tests**

Replace the existing run model assertions in `tests/test_models.py` with SOP quality assertions:

```python
from app.models.sop_quality_checks import SopQualityCheck, SopQualityEvent


def test_sop_quality_check_model_table_name() -> None:
    assert SopQualityCheck.__tablename__ == "sop_quality_checks"


def test_sop_quality_check_has_subject_environment_columns() -> None:
    columns = SopQualityCheck.__table__.columns

    assert columns["sop_id"].nullable is False
    assert columns["env_key"].nullable is False
    assert columns["thread_id"].nullable is False
    assert columns["checkpoint_ns"].nullable is False
    assert columns["sop_snapshot"].nullable is False
    assert "env_snapshot" not in columns
    assert "input_snapshot" not in columns


def test_sop_quality_check_active_unique_index() -> None:
    index = next(
        index
        for index in SopQualityCheck.__table__.indexes
        if index.name == "uq_sop_quality_checks_active_subject_env"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["sop_id", "env_key"]
    where = str(index.dialect_options["postgresql"]["where"])
    assert "pending" in where
    assert "running" in where


def test_sop_quality_event_model_has_no_payload_column() -> None:
    columns = SopQualityEvent.__table__.columns

    assert SopQualityEvent.__tablename__ == "sop_quality_events"
    assert "payload" not in columns
    assert columns["check_id"].nullable is False
    assert columns["sequence"].nullable is False
```

Update `tests/test_migrations.py` so the single Alembic head remains `20260527_0004`.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_models.py::test_sop_quality_check_model_table_name tests/test_models.py::test_sop_quality_event_model_has_no_payload_column -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.sop_quality_checks'`.

**Step 3: Implement models**

Create `app/models/sop_quality_checks.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SopQualityCheck(Base):
    __tablename__ = "sop_quality_checks"
    __table_args__ = (
        Index(
            "uq_sop_quality_checks_active_subject_env",
            "sop_id",
            "env_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
        Index(
            "ix_sop_quality_checks_subject_history",
            "sop_id",
            "env_key",
            "created_at",
        ),
        Index("ix_sop_quality_checks_env_history", "env_key", "created_at"),
        Index("ix_sop_quality_checks_status_updated", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    sop_id: Mapped[str] = mapped_column(Text, nullable=False)
    env_key: Mapped[str] = mapped_column(Text, nullable=False)
    graph_name: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_ns: Mapped[str] = mapped_column(Text, nullable=False)
    current_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_result: Mapped[str | None] = mapped_column(Text)
    sop_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["SopQualityEvent"]] = relationship(
        back_populates="check",
        cascade="all, delete-orphan",
    )


class SopQualityEvent(Base):
    __tablename__ = "sop_quality_events"
    __table_args__ = (
        Index("uq_sop_quality_events_check_sequence", "check_id", "sequence", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_id: Mapped[UUID] = mapped_column(
        ForeignKey("sop_quality_checks.id"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    node: Mapped[str | None] = mapped_column(Text)
    checkpoint_id: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    check: Mapped[SopQualityCheck] = relationship(back_populates="events")
```

Modify `app/models/__init__.py` to export `SopQualityCheck` and `SopQualityEvent` and remove `Run`/`RunEvent`.

**Step 4: Replace the base migration**

Run:

```bash
git mv migrations/versions/20260525_0001_create_runs.py migrations/versions/20260525_0001_create_sop_quality_checks.py
```

Rewrite the migration to keep `revision = "20260525_0001"` and `down_revision = None`, but create `sop_quality_checks` and `sop_quality_events` instead of `runs` and `run_events`.

The migration must create:

```python
op.create_table(
    "sop_quality_checks",
    sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("sop_id", sa.Text(), nullable=False),
    sa.Column("env_key", sa.Text(), nullable=False),
    sa.Column("graph_name", sa.Text(), nullable=False),
    sa.Column("graph_version", sa.Text(), nullable=False),
    sa.Column("thread_id", sa.Text(), nullable=False),
    sa.Column("checkpoint_ns", sa.Text(), nullable=False),
    sa.Column("current_checkpoint_id", sa.Text(), nullable=True),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("quality_result", sa.Text(), nullable=True),
    sa.Column("sop_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("created_by", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint("id"),
)
op.create_index(
    "uq_sop_quality_checks_active_subject_env",
    "sop_quality_checks",
    ["sop_id", "env_key"],
    unique=True,
    postgresql_where=sa.text("status IN ('pending', 'running')"),
)
```

Also create the three non-unique history indexes and the `sop_quality_events` table with `uq_sop_quality_events_check_sequence`.

**Step 5: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_models.py tests/test_migrations.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/models/sop_quality_checks.py app/models/__init__.py migrations/versions/20260525_0001_create_sop_quality_checks.py tests/test_models.py tests/test_migrations.py
git add -u migrations/versions/20260525_0001_create_runs.py
git commit -m "feat: add sop quality check storage models"
```

---

### Task 3: SOP Quality Repository

**Files:**
- Create: `app/repositories/sop_quality_checks.py`
- Modify: `app/repositories/__init__.py`
- Create: `tests/test_sop_quality_check_repository.py`

**Step 1: Write failing repository tests**

Create `tests/test_sop_quality_check_repository.py`:

```python
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.sop_quality_checks import (
    ActiveSopQualityCheckExistsError,
    SopQualityCheckRepository,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.db,
    pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"),
        reason="set TEST_DATABASE_URL to run repository integration tests",
    ),
]


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


async def test_create_check_persists_business_fields(session) -> None:
    repository = SopQualityCheckRepository(session)

    check = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist", "payload": {}},
    )

    assert check.sop_id == "release-checklist"
    assert check.env_key == "dev"
    assert check.status == "pending"
    assert check.thread_id
    assert check.checkpoint_ns == "sop_quality"


async def test_duplicate_active_check_returns_active_id(session) -> None:
    repository = SopQualityCheckRepository(session)
    first = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )

    with pytest.raises(ActiveSopQualityCheckExistsError) as exc_info:
        await repository.create_check(
            sop_id="release-checklist",
            env_key="dev",
            graph_name="sop_quality",
            graph_version="sop-quality@1",
            sop_snapshot={"sop_id": "release-checklist"},
        )

    assert exc_info.value.active_check_id == first.id


async def test_terminal_check_does_not_block_new_check(session) -> None:
    repository = SopQualityCheckRepository(session)
    first = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )
    await repository.mark_terminal(first.id, "succeeded", quality_result="pass", result={})

    second = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )

    assert second.id != first.id


async def test_append_event_increments_sequence_without_payload(session) -> None:
    repository = SopQualityCheckRepository(session)
    check = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )

    first = await repository.append_event(check.id, event_type="created")
    second = await repository.append_event(
        check.id,
        event_type="checkpoint",
        node="check_steps",
        checkpoint_id="checkpoint-1",
        message="Checkpoint saved.",
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert not hasattr(second, "payload")


async def test_interrupt_active_checks_on_startup(session) -> None:
    repository = SopQualityCheckRepository(session)
    check = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )
    await repository.mark_running(check.id)

    interrupted = await repository.interrupt_active_checks_on_startup()

    assert [item.id for item in interrupted] == [check.id]
    assert interrupted[0].status == "interrupted"
    events = await repository.get_events_after(check.id)
    assert events[-1].type == "interrupted"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_sop_quality_check_repository.py -q
```

Expected without `TEST_DATABASE_URL`: SKIPPED. With `TEST_DATABASE_URL`: FAIL with missing repository module.

**Step 3: Implement repository**

Create `app/repositories/sop_quality_checks.py` with these public methods:

```python
ACTIVE_CHECK_STATUSES = {"pending", "running"}


class ActiveSopQualityCheckExistsError(Exception):
    def __init__(self, active_check_id: UUID) -> None:
        self.active_check_id = active_check_id
        super().__init__(str(active_check_id))


class SopQualityCheckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_check(
        self,
        *,
        sop_id: str,
        env_key: str,
        graph_name: str,
        graph_version: str,
        sop_snapshot: dict[str, Any],
        created_by: str | None = None,
    ) -> SopQualityCheck:
        active = await self.get_active_check(sop_id=sop_id, env_key=env_key)
        if active is not None:
            raise ActiveSopQualityCheckExistsError(active.id)

        check = SopQualityCheck(
            sop_id=sop_id,
            env_key=env_key,
            graph_name=graph_name,
            graph_version=graph_version,
            thread_id=str(uuid4()),
            checkpoint_ns=graph_name,
            status="pending",
            sop_snapshot=sop_snapshot,
            created_by=created_by,
        )
        self._session.add(check)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            active = await self.get_active_check(sop_id=sop_id, env_key=env_key)
            if active is not None:
                raise ActiveSopQualityCheckExistsError(active.id) from exc
            raise
        return check
```

Also implement:

- `get_check(check_id: UUID) -> SopQualityCheck | None`, setting `latest_sequence` dynamically.
- `get_active_check(sop_id: str, env_key: str) -> SopQualityCheck | None`.
- `list_checks(sop_id: str | None, env_key: str | None, limit: int) -> list[SopQualityCheck]`.
- `mark_running(check_id: UUID) -> SopQualityCheck`.
- `mark_terminal(check_id: UUID, status: str, quality_result: str | None = None, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> SopQualityCheck`.
- `set_current_checkpoint(check_id: UUID, checkpoint_id: str) -> SopQualityCheck`.
- `append_event(check_id: UUID, event_type: str, node: str | None = None, checkpoint_id: str | None = None, task_id: str | None = None, message: str | None = None) -> SopQualityEvent`.
- `get_events_after(check_id: UUID, after: int = 0, limit: int = 100) -> list[SopQualityEvent]`.
- `interrupt_active_checks_on_startup() -> list[SopQualityCheck]`.
- `commit() -> None`.

Use `select(...).with_for_update()` before calculating the next event sequence.

Modify `app/repositories/__init__.py` to export `ActiveSopQualityCheckExistsError` and `SopQualityCheckRepository`.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_sop_quality_check_repository.py tests/test_models.py -q
```

Expected: repository tests skip without DB or pass with DB; model tests pass.

**Step 5: Commit**

```bash
git add app/repositories/sop_quality_checks.py app/repositories/__init__.py tests/test_sop_quality_check_repository.py
git commit -m "feat: add sop quality check repository"
```

---

### Task 4: Schemas And Service Create-Or-Join Flow

**Files:**
- Create: `app/schemas/sop_quality_checks.py`
- Modify: `app/schemas/__init__.py`
- Modify: `app/services/sop_quality.py`
- Create: `tests/test_sop_quality_check_schemas.py`
- Replace: `tests/test_sop_quality_service.py`

**Step 1: Write failing schema tests**

Create `tests/test_sop_quality_check_schemas.py`:

```python
from uuid import uuid4

from app.schemas.sop_quality_checks import (
    SopQualityCheckEvent,
    SopQualityCheckStartResponse,
    SopQualityCheckStatus,
)


def test_start_response_uses_check_id_not_run_id() -> None:
    check_id = uuid4()

    payload = SopQualityCheckStartResponse(
        check_id=check_id,
        status=SopQualityCheckStatus.pending,
        created=True,
        status_url=f"/api/sop-quality-checks/{check_id}",
        stream_url=f"/api/sop-quality-checks/{check_id}/stream",
    ).model_dump(mode="json")

    assert payload["check_id"] == str(check_id)
    assert "run_id" not in payload


def test_event_schema_has_no_payload() -> None:
    fields = SopQualityCheckEvent.model_fields

    assert "payload" not in fields
    assert "message" in fields
```

**Step 2: Replace service tests**

Rewrite `tests/test_sop_quality_service.py` around `start_check`:

```python
from uuid import UUID, uuid4

import pytest

from app.core.config import EnvironmentConfig, Settings
from app.repositories.sop_quality_checks import ActiveSopQualityCheckExistsError
from app.schemas.sop import SopSnapshot
from app.services.sop_quality import SopQualityService


class FakeSopClient:
    def __init__(self, order: list[str]) -> None:
        self._order = order

    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        self._order.append("fetch_sop")
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="test",
            updated_at=None,
            payload={"id": sop_id},
        )


class FakeRepository:
    def __init__(self, order: list[str], active_check_id: UUID | None = None) -> None:
        self.order = order
        self.active_check_id = active_check_id
        self.created_kwargs = {}
        self.id = uuid4()
        self.status = "pending"

    async def create_check(self, **kwargs):
        self.order.append("create_check")
        self.created_kwargs = kwargs
        if self.active_check_id is not None:
            raise ActiveSopQualityCheckExistsError(self.active_check_id)
        return self

    async def get_check(self, check_id):
        if self.active_check_id == check_id:
            active = FakeRepository([])
            active.id = check_id
            active.status = "running"
            return active
        return None

    async def append_event(self, check_id, **kwargs):
        self.order.append(kwargs["event_type"])
        return None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environments=[
            EnvironmentConfig(key="dev", name_zh="dev", name_en="Development")
        ]
    )


@pytest.mark.asyncio
async def test_start_check_fetches_sop_before_creating_check(settings: Settings) -> None:
    order: list[str] = []
    service = SopQualityService(
        settings=settings,
        sop_client=FakeSopClient(order),
        repository=FakeRepository(order),
    )

    await service.start_check("release-checklist", "dev")

    assert order[:2] == ["fetch_sop", "create_check"]


@pytest.mark.asyncio
async def test_start_check_returns_existing_active_check(settings: Settings) -> None:
    active_check_id = uuid4()
    service = SopQualityService(
        settings=settings,
        sop_client=FakeSopClient([]),
        repository=FakeRepository([], active_check_id=active_check_id),
    )

    result = await service.start_check("release-checklist", "dev")

    assert result.created is False
    assert result.check_id == active_check_id
    assert result.status_url == f"/api/sop-quality-checks/{active_check_id}"
```

**Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_sop_quality_check_schemas.py tests/test_sop_quality_service.py -q
```

Expected: FAIL with missing schema/service names.

**Step 4: Implement schemas**

Create `app/schemas/sop_quality_checks.py`:

```python
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SopQualityCheckStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    interrupted = "interrupted"


class SopQualityCheckStartResponse(BaseModel):
    check_id: UUID
    status: SopQualityCheckStatus
    created: bool
    status_url: str
    stream_url: str


class SopQualityCheckSummary(BaseModel):
    check_id: UUID
    sop_id: str
    env_key: str
    status: SopQualityCheckStatus
    quality_result: str | None = None
    latest_sequence: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_summary: str | None = None


class SopQualityDisplayState(BaseModel):
    model_config = ConfigDict(extra="allow")

    latest_sequence: int = 0
    nodes: dict[str, Any] = {}
    is_running: bool = False


class SopQualityCheckDetail(SopQualityCheckSummary):
    graph_name: str
    graph_version: str
    thread_id: str
    checkpoint_ns: str
    current_checkpoint_id: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    display_state: SopQualityDisplayState


class SopQualityCheckEvent(BaseModel):
    check_id: UUID
    sequence: int
    type: str
    node: str | None = None
    checkpoint_id: str | None = None
    task_id: str | None = None
    message: str | None = None
    created_at: datetime | None = None
```

**Step 5: Implement service**

Replace `app/services/sop_quality.py` so it depends on `SopQualityCheckRepository`, not `RunRepository`.

Key dataclass:

```python
@dataclass(frozen=True)
class CheckStartResult:
    check_id: UUID
    status: SopQualityCheckStatus
    created: bool
    status_url: str
    stream_url: str
```

Key service behavior:

```python
async def start_check(
    self,
    sop_id: str,
    env_key: str,
    created_by: str | None = None,
) -> CheckStartResult:
    self._settings.get_environment(env_key)
    sop_snapshot = await self._sop_client.get_sop(sop_id, env_key)
    try:
        check = await self._repository.create_check(
            sop_id=sop_id,
            env_key=env_key,
            graph_name=SOP_QUALITY_GRAPH_NAME,
            graph_version=SOP_QUALITY_GRAPH_VERSION,
            sop_snapshot=sop_snapshot.model_dump(mode="json"),
            created_by=created_by,
        )
    except ActiveSopQualityCheckExistsError as exc:
        active = await self._repository.get_check(exc.active_check_id)
        status = SopQualityCheckStatus(active.status if active else "running")
        return self._result(exc.active_check_id, status=status, created=False)

    await self._repository.append_event(check.id, event_type="created")
    await self._commit()
    await self._schedule_if_configured(check.id)
    return self._result(check.id, status=SopQualityCheckStatus.pending, created=True)
```

Do not schedule a new runner for an existing active check.

**Step 6: Run tests**

Run:

```bash
uv run pytest tests/test_sop_quality_check_schemas.py tests/test_sop_quality_service.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add app/schemas/sop_quality_checks.py app/schemas/__init__.py app/services/sop_quality.py tests/test_sop_quality_check_schemas.py tests/test_sop_quality_service.py
git commit -m "feat: add sop quality check service"
```

---

### Task 5: LangGraph Checkpoint Helper

**Files:**
- Create: `app/core/checkpoints.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/test_checkpoints.py`

**Step 1: Write failing checkpoint helper tests**

Create `tests/test_checkpoints.py`:

```python
from app.core.checkpoints import postgres_checkpoint_url


def test_postgres_checkpoint_url_strips_asyncpg_driver() -> None:
    assert postgres_checkpoint_url(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/db"
    ) == "postgresql://postgres:postgres@localhost:5432/db"


def test_postgres_checkpoint_url_leaves_plain_url_unchanged() -> None:
    assert postgres_checkpoint_url("postgresql://localhost/db") == (
        "postgresql://localhost/db"
    )
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_checkpoints.py -q
```

Expected: FAIL with missing module.

**Step 3: Add dependency**

Add to `pyproject.toml` dependencies if absent:

```toml
"psycopg[binary]>=3.3.4",
```

Run:

```bash
uv lock
```

Expected: `uv.lock` updated.

**Step 4: Implement helper**

Create `app/core/checkpoints.py`:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings


def postgres_checkpoint_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return f"postgresql://{database_url.removeprefix('postgresql+asyncpg://')}"
    if database_url.startswith("postgres+asyncpg://"):
        return f"postgres://{database_url.removeprefix('postgres+asyncpg://')}"
    return database_url


@asynccontextmanager
async def open_postgres_checkpointer(
    database_url: str | None = None,
    *,
    setup: bool = False,
) -> AsyncIterator[AsyncPostgresSaver]:
    checkpoint_url = postgres_checkpoint_url(database_url or settings.database_url)
    async with AsyncPostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
        if setup:
            await checkpointer.setup()
        yield checkpointer
```

**Step 5: Run tests**

Run:

```bash
uv run pytest tests/test_checkpoints.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/core/checkpoints.py pyproject.toml uv.lock tests/test_checkpoints.py
git commit -m "feat: add langgraph postgres checkpoint helper"
```

---

### Task 6: Code-Defined SOP Quality Graph

**Files:**
- Create: `app/agent/sop_quality/constants.py`
- Modify: `app/agent/sop_quality/state.py`
- Create: `app/agent/sop_quality/nodes/load_sop.py`
- Create: `app/agent/sop_quality/nodes/check_steps.py`
- Create: `app/agent/sop_quality/nodes/summarize_result.py`
- Modify: `app/agent/sop_quality/graph.py`
- Modify: `app/agent/sop_quality/__init__.py`
- Replace: `tests/test_graph_runner.py` with `tests/test_sop_quality_graph.py`

**Step 1: Write failing graph tests**

Create `tests/test_sop_quality_graph.py`:

```python
import pytest

from app.agent.sop_quality.graph import build_sop_quality_graph


@pytest.mark.asyncio
async def test_sop_quality_graph_returns_result_for_valid_sop() -> None:
    graph = build_sop_quality_graph()

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {
                "sop_id": "release-checklist",
                "payload": {"title": "Release", "steps": [{"name": "deploy"}]},
            },
        }
    )

    assert result["quality_result"] in {"pass", "warn"}
    assert "result" in result
    assert result["result"]["quality_result"] == result["quality_result"]


@pytest.mark.asyncio
async def test_sop_quality_graph_flags_missing_steps() -> None:
    graph = build_sop_quality_graph()

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {
                "sop_id": "release-checklist",
                "payload": {"title": "Release"},
            },
        }
    )

    assert result["quality_result"] == "warn"
    assert result["findings"][0]["title"] == "Missing SOP steps"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_sop_quality_graph.py -q
```

Expected: FAIL because `build_sop_quality_graph` does not exist.

**Step 3: Add graph constants and state**

Create `app/agent/sop_quality/constants.py`:

```python
SOP_QUALITY_GRAPH_NAME = "sop_quality"
SOP_QUALITY_GRAPH_VERSION = "sop-quality@1"
```

Modify `app/agent/sop_quality/state.py`:

```python
from typing import Any, TypedDict


class SopQualityState(TypedDict, total=False):
    check_id: str
    sop_id: str
    env_key: str
    sop_snapshot: dict[str, Any]
    messages: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    summary: str
    quality_result: str
    report_markdown: str
    result: dict[str, Any]
```

**Step 4: Implement deterministic first-phase nodes**

Create `app/agent/sop_quality/nodes/load_sop.py`:

```python
from app.agent.sop_quality.state import SopQualityState


async def load_sop(state: SopQualityState) -> SopQualityState:
    sop_id = state.get("sop_id") or state.get("sop_snapshot", {}).get("sop_id", "")
    return {
        "messages": [
            {
                "role": "assistant",
                "content": f"Loaded SOP {sop_id}.",
            }
        ]
    }
```

Create `app/agent/sop_quality/nodes/check_steps.py`:

```python
from typing import Any

from app.agent.sop_quality.state import SopQualityState


async def check_steps(state: SopQualityState) -> SopQualityState:
    payload = _payload(state)
    findings: list[dict[str, Any]] = []

    if not payload.get("title"):
        findings.append(
            {
                "severity": "medium",
                "title": "Missing SOP title",
                "recommendation": "Add a clear SOP title.",
            }
        )

    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        findings.append(
            {
                "severity": "high",
                "title": "Missing SOP steps",
                "recommendation": "Add executable SOP steps before quality approval.",
            }
        )

    quality_result = "pass" if not findings else "warn"
    return {"findings": findings, "quality_result": quality_result}


def _payload(state: SopQualityState) -> dict[str, Any]:
    snapshot = state.get("sop_snapshot") or {}
    payload = snapshot.get("payload")
    return payload if isinstance(payload, dict) else {}
```

Create `app/agent/sop_quality/nodes/summarize_result.py`:

```python
from app.agent.sop_quality.state import SopQualityState


async def summarize_result(state: SopQualityState) -> SopQualityState:
    findings = state.get("findings", [])
    quality_result = state.get("quality_result", "pass")
    summary = (
        "No blocking SOP quality issues found."
        if not findings
        else f"Found {len(findings)} SOP quality issue(s)."
    )
    report_markdown = _report_markdown(summary, findings)
    return {
        "summary": summary,
        "report_markdown": report_markdown,
        "result": {
            "quality_result": quality_result,
            "summary": summary,
            "findings": findings,
            "report_markdown": report_markdown,
        },
    }


def _report_markdown(summary: str, findings: list[dict]) -> str:
    if not findings:
        return f"## SOP Quality Report\n\n{summary}\n"
    lines = ["## SOP Quality Report", "", summary, ""]
    for finding in findings:
        lines.append(f"- **{finding['severity']}** {finding['title']}: {finding['recommendation']}")
    return "\n".join(lines)
```

**Step 5: Implement graph assembly**

Replace `app/agent/sop_quality/graph.py` with a code-defined graph:

```python
from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.sop_quality.nodes.check_steps import check_steps
from app.agent.sop_quality.nodes.load_sop import load_sop
from app.agent.sop_quality.nodes.summarize_result import summarize_result
from app.agent.sop_quality.state import SopQualityState


def build_sop_quality_graph(checkpointer: Any | None = None):
    builder = StateGraph(SopQualityState)
    builder.add_node("load_sop", load_sop)
    builder.add_node("check_steps", check_steps)
    builder.add_node("summarize_result", summarize_result)
    builder.set_entry_point("load_sop")
    builder.add_edge("load_sop", "check_steps")
    builder.add_edge("check_steps", "summarize_result")
    builder.add_edge("summarize_result", END)
    return builder.compile(checkpointer=checkpointer)
```

Modify `app/agent/sop_quality/__init__.py` to export `build_sop_quality_graph`, `SOP_QUALITY_GRAPH_NAME`, and `SOP_QUALITY_GRAPH_VERSION`. Remove `SOP_QUALITY_AGENT_KEY`, `run_sop_quality_graph`, `run_sop_quality_graph_with_new_session`, and `stream_sop_quality_agent` exports.

**Step 6: Run tests**

Run:

```bash
uv run pytest tests/test_sop_quality_graph.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add app/agent/sop_quality tests/test_sop_quality_graph.py
git rm tests/test_graph_runner.py
git commit -m "feat: define sop quality langgraph"
```

---

### Task 7: Runner, Checkpoint State Display, And Broadcast

**Files:**
- Create: `app/services/sop_quality_runner.py`
- Create: `app/services/sop_quality_streaming.py`
- Create: `app/agent/sop_quality/display.py`
- Create: `tests/test_sop_quality_runner.py`
- Create: `tests/test_sop_quality_streaming.py`

**Step 1: Write failing broadcast tests**

Create `tests/test_sop_quality_streaming.py`:

```python
from uuid import uuid4

import pytest

from app.services.sop_quality_streaming import SopQualityBroadcast


@pytest.mark.asyncio
async def test_broadcast_delivers_message_to_all_subscribers() -> None:
    check_id = uuid4()
    broadcast = SopQualityBroadcast()

    async with broadcast.subscribe(check_id) as first:
        async with broadcast.subscribe(check_id) as second:
            await broadcast.publish(
                check_id,
                {"type": "live", "node": "check_steps", "message": "Checking."},
            )

            assert await first.get() == {
                "type": "live",
                "node": "check_steps",
                "message": "Checking.",
            }
            assert await second.get() == {
                "type": "live",
                "node": "check_steps",
                "message": "Checking.",
            }
```

**Step 2: Write failing runner tests**

Create `tests/test_sop_quality_runner.py` with fakes:

```python
from uuid import uuid4

import pytest

from app.services.sop_quality_runner import run_sop_quality_check


class FakeCheck:
    def __init__(self) -> None:
        self.id = uuid4()
        self.sop_id = "release-checklist"
        self.env_key = "dev"
        self.thread_id = "thread-1"
        self.checkpoint_ns = "sop_quality"
        self.current_checkpoint_id = None
        self.sop_snapshot = {"sop_id": "release-checklist", "payload": {"title": "Release"}}


class FakeRepository:
    def __init__(self, check: FakeCheck) -> None:
        self.check = check
        self.events: list[dict] = []
        self.terminal = None

    async def get_check(self, check_id):
        return self.check if check_id == self.check.id else None

    async def mark_running(self, check_id):
        self.events.append({"type": "mark_running"})
        return self.check

    async def append_event(self, check_id, **kwargs):
        self.events.append(kwargs)
        return type("Event", (), {"sequence": len(self.events), **kwargs})()

    async def set_current_checkpoint(self, check_id, checkpoint_id):
        self.check.current_checkpoint_id = checkpoint_id
        return self.check

    async def mark_terminal(self, check_id, status, **kwargs):
        self.terminal = {"status": status, **kwargs}
        return self.check

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_runner_marks_success_and_writes_lifecycle_events() -> None:
    check = FakeCheck()
    repository = FakeRepository(check)

    result = await run_sop_quality_check(check.id, repository, checkpointer=None)

    assert result["status"] == "succeeded"
    assert repository.events[1]["event_type"] == "started"
    assert repository.terminal["status"] == "succeeded"
    assert repository.terminal["result"]["quality_result"] in {"pass", "warn"}
```

**Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_sop_quality_streaming.py tests/test_sop_quality_runner.py -q
```

Expected: FAIL with missing modules.

**Step 4: Implement broadcast**

Create `app/services/sop_quality_streaming.py`:

```python
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID


class SopQualityBroadcast:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(self, check_id: UUID) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[check_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[check_id].discard(queue)
            if not self._subscribers[check_id]:
                self._subscribers.pop(check_id, None)

    async def publish(self, check_id: UUID, message: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(check_id, ())):
            await queue.put(dict(message))
```

**Step 5: Implement display state conversion**

Create `app/agent/sop_quality/display.py`:

```python
from typing import Any


def display_state_from_graph_values(
    values: dict[str, Any],
    *,
    latest_sequence: int = 0,
    is_running: bool = False,
) -> dict[str, Any]:
    findings = values.get("findings") if isinstance(values.get("findings"), list) else []
    result = values.get("result") if isinstance(values.get("result"), dict) else None
    nodes: dict[str, Any] = {}
    if values.get("sop_snapshot"):
        nodes["load_sop"] = {"status": "done", "streamText": "SOP snapshot loaded."}
    if findings is not None:
        nodes["check_steps"] = {
            "status": "done" if not is_running else "running",
            "streamText": _findings_text(findings),
        }
    if result:
        nodes["summarize_result"] = {
            "status": "done",
            "streamText": result.get("report_markdown") or result.get("summary") or "",
        }
    return {
        "latest_sequence": latest_sequence,
        "nodes": nodes,
        "is_running": is_running,
    }


def _findings_text(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "No obvious structural issues found."
    return "\n".join(f"- {item.get('title', 'Finding')}" for item in findings)
```

**Step 6: Implement runner**

Create `app/services/sop_quality_runner.py`:

```python
from typing import Any
from uuid import UUID

from app.agent.sop_quality.graph import build_sop_quality_graph
from app.core.checkpoints import open_postgres_checkpointer
from app.core.database import async_session
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.services.sop_quality_streaming import SopQualityBroadcast


async def run_sop_quality_check(
    check_id: UUID,
    repository: SopQualityCheckRepository,
    *,
    checkpointer: Any,
    broadcast: SopQualityBroadcast | None = None,
) -> dict[str, Any]:
    check = await repository.mark_running(check_id)
    await repository.append_event(check_id, event_type="started", message="SOP quality check started.")
    await repository.commit()
    if broadcast is not None:
        await broadcast.publish(check_id, {"type": "started"})

    graph = build_sop_quality_graph(checkpointer=checkpointer)
    config = {
        "configurable": {
            "thread_id": check.thread_id,
            "checkpoint_ns": check.checkpoint_ns,
        }
    }
    initial_state = {
        "check_id": str(check.id),
        "sop_id": check.sop_id,
        "env_key": check.env_key,
        "sop_snapshot": check.sop_snapshot,
    }

    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        snapshot = await graph.aget_state(config)
        checkpoint_id = _checkpoint_id_from_config(snapshot.config)
        if checkpoint_id is not None:
            await repository.set_current_checkpoint(check_id, checkpoint_id)
            await repository.append_event(
                check_id,
                event_type="checkpoint",
                checkpoint_id=checkpoint_id,
                message="Checkpoint saved.",
            )
        await repository.mark_terminal(
            check_id,
            "succeeded",
            quality_result=final_state.get("quality_result"),
            result=final_state.get("result"),
        )
        await repository.append_event(check_id, event_type="completed", message="SOP quality check completed.")
        await repository.commit()
        if broadcast is not None:
            await broadcast.publish(check_id, {"type": "completed"})
        return {"status": "succeeded", "result": final_state.get("result")}
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        await repository.mark_terminal(check_id, "failed", error=error)
        await repository.append_event(check_id, event_type="failed", message=str(exc))
        await repository.commit()
        if broadcast is not None:
            await broadcast.publish(check_id, {"type": "failed", "message": str(exc)})
        return {"status": "failed", "error": error}


async def run_sop_quality_check_with_new_session(
    check_id: UUID,
    broadcast: SopQualityBroadcast | None = None,
) -> dict[str, Any]:
    async with async_session() as session:
        repository = SopQualityCheckRepository(session)
        async with open_postgres_checkpointer(setup=True) as checkpointer:
            return await run_sop_quality_check(
                check_id,
                repository,
                checkpointer=checkpointer,
                broadcast=broadcast,
            )


def _checkpoint_id_from_config(config: dict[str, Any] | None) -> str | None:
    configurable = (config or {}).get("configurable")
    if not isinstance(configurable, dict):
        return None
    checkpoint_id = configurable.get("checkpoint_id")
    return checkpoint_id if isinstance(checkpoint_id, str) else None
```

**Step 7: Run tests**

Run:

```bash
uv run pytest tests/test_sop_quality_streaming.py tests/test_sop_quality_runner.py tests/test_sop_quality_graph.py -q
```

Expected: PASS.

**Step 8: Commit**

```bash
git add app/services/sop_quality_runner.py app/services/sop_quality_streaming.py app/agent/sop_quality/display.py tests/test_sop_quality_runner.py tests/test_sop_quality_streaming.py
git commit -m "feat: run sop quality graph with checkpoint lifecycle"
```

---

### Task 8: SOP Quality Checks API And SSE

**Files:**
- Create: `app/api/v1/sop_quality_checks.py`
- Modify: `app/api/deps.py`
- Modify: `app/main.py`
- Modify: `app/api/v1/__init__.py`
- Replace: `tests/test_sop_api.py` SOP run cases with `tests/test_sop_quality_checks_api.py`
- Replace: `tests/test_runs_api.py` with SSE tests for checks

**Step 1: Write failing API tests**

Create `tests/test_sop_quality_checks_api.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_session, get_sop_client, get_sop_quality_check_repository
from app.main import app
from app.schemas.sop import SopSnapshot


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeSopClient:
    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="test",
            updated_at=None,
            payload={"id": sop_id, "title": "Release"},
        )


class FakeCheck:
    def __init__(self, check_id=None) -> None:
        self.id = check_id or uuid4()
        self.sop_id = "release-checklist"
        self.env_key = "dev"
        self.graph_name = "sop_quality"
        self.graph_version = "sop-quality@1"
        self.thread_id = "thread-1"
        self.checkpoint_ns = "sop_quality"
        self.current_checkpoint_id = None
        self.status = "pending"
        self.quality_result = None
        self.result = None
        self.error = None
        self.created_at = datetime.now(UTC)
        self.started_at = None
        self.finished_at = None
        self.latest_sequence = 0


class FakeRepository:
    def __init__(self) -> None:
        self.check = FakeCheck()
        self.events = []

    async def create_check(self, **kwargs):
        return self.check

    async def get_check(self, check_id):
        return self.check if check_id == self.check.id else None

    async def append_event(self, check_id, **kwargs):
        event = type(
            "Event",
            (),
            {
                "check_id": check_id,
                "sequence": len(self.events) + 1,
                "created_at": datetime.now(UTC),
                **kwargs,
            },
        )()
        self.events.append(event)
        return event

    async def get_events_after(self, check_id, *, after=0, limit=100):
        return [event for event in self.events if event.sequence > after]

    async def list_checks(self, **kwargs):
        return [self.check]


def make_session_override(session: FakeSession):
    async def override_session():
        yield session

    return override_session


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    app.state.scheduled_check_ids = []

    async def fake_executor(check_id):
        app.state.scheduled_check_ids.append(str(check_id))

    app.state.sop_quality_check_executor = fake_executor
    yield
    app.dependency_overrides.clear()
    del app.state.scheduled_check_ids
    del app.state.sop_quality_check_executor


@pytest.mark.asyncio
async def test_start_check_returns_accepted_and_schedules_runner() -> None:
    session = FakeSession()
    repository = FakeRepository()
    app.dependency_overrides[get_session] = make_session_override(session)
    app.dependency_overrides[get_sop_client] = FakeSopClient
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/sop-quality-checks?sop_id=release-checklist&env=dev")

    assert response.status_code == 202
    body = response.json()
    assert body["check_id"] == str(repository.check.id)
    assert body["created"] is True
    assert app.state.scheduled_check_ids == [str(repository.check.id)]


@pytest.mark.asyncio
async def test_get_check_detail_returns_display_state() -> None:
    repository = FakeRepository()
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/sop-quality-checks/{repository.check.id}")

    assert response.status_code == 200
    assert response.json()["check_id"] == str(repository.check.id)
    assert "display_state" in response.json()
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_sop_quality_checks_api.py -q
```

Expected: FAIL with missing dependency/router.

**Step 3: Add repository dependency**

Modify `app/api/deps.py`:

```python
from app.repositories.sop_quality_checks import SopQualityCheckRepository


def get_sop_quality_check_repository(session: SessionDep) -> SopQualityCheckRepository:
    return SopQualityCheckRepository(session)


SopQualityCheckRepositoryDep = Annotated[
    SopQualityCheckRepository,
    Depends(get_sop_quality_check_repository),
]
```

Remove `RunRepositoryDep` after old run deletion in Task 10.

**Step 4: Implement API router**

Create `app/api/v1/sop_quality_checks.py`:

```python
import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import SessionDep, SopClientDep, SopQualityCheckRepositoryDep
from app.core.config import settings
from app.schemas.sop_quality_checks import (
    SopQualityCheckDetail,
    SopQualityCheckEvent,
    SopQualityCheckStartResponse,
)
from app.services.sop_client import SopClientError, SopNotFoundError
from app.services.sop_quality import SopQualityService
from app.services.sop_quality_runner import run_sop_quality_check_with_new_session

router = APIRouter(prefix="/api/sop-quality-checks", tags=["sop-quality-checks"])
SSE_POLL_INTERVAL_SECONDS = 0.5
TERMINAL_CHECK_STATUSES = {"succeeded", "failed", "cancelled", "interrupted"}


@router.post("")
async def start_sop_quality_check(
    background_tasks: BackgroundTasks,
    request: Request,
    session: SessionDep,
    sop_client: SopClientDep,
    repository: SopQualityCheckRepositoryDep,
    sop_id: Annotated[str, Query(min_length=1)],
    env: Annotated[str, Query(min_length=1)],
) -> JSONResponse:
    def schedule_check(check_id: UUID) -> None:
        executor = getattr(
            request.app.state,
            "sop_quality_check_executor",
            run_sop_quality_check_with_new_session,
        )
        background_tasks.add_task(executor, check_id)

    service = SopQualityService(
        settings=settings,
        sop_client=sop_client,
        repository=repository,
        schedule_check=schedule_check,
        commit=session.commit,
    )
    try:
        result = await service.start_check(sop_id, env)
    except SopNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except SopClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY) from exc

    status_code = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
    return JSONResponse(
        status_code=status_code,
        content=SopQualityCheckStartResponse(**result.__dict__).model_dump(mode="json"),
    )
```

Also implement:

- `GET /api/sop-quality-checks/{check_id}` returning `SopQualityCheckDetail`.
- `GET /api/sop-quality-checks/{check_id}/events?after=`.
- `GET /api/sop-quality-checks/{check_id}/stream?after=`.
- `GET /api/sop-quality-checks?sop_id=&env=&limit=`.

SSE formatter:

```python
def format_sse(event: dict[str, object]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    return f"id: {event['sequence']}\nevent: {event['type']}\ndata: {data}\n\n"
```

Event dict must not include `payload`.

**Step 5: Register router and startup cleanup**

Modify `app/main.py`:

- Import `sop_quality_checks`.
- Include `app.include_router(sop_quality_checks.router)`.
- Replace `interrupt_leftover_runs()` with `interrupt_leftover_sop_quality_checks()` using `SopQualityCheckRepository.interrupt_active_checks_on_startup()`.
- Remove `runs.router` after Task 10.

Modify `app/api/v1/__init__.py` to include `sop_quality_checks`.

**Step 6: Run API tests**

Run:

```bash
uv run pytest tests/test_sop_quality_checks_api.py tests/test_sop_api.py tests/test_startup_cleanup.py -q
```

Expected: PASS after updating old startup cleanup tests to use checks instead of runs.

**Step 7: Commit**

```bash
git add app/api/v1/sop_quality_checks.py app/api/deps.py app/main.py app/api/v1/__init__.py tests/test_sop_quality_checks_api.py tests/test_sop_api.py tests/test_startup_cleanup.py
git commit -m "feat: expose sop quality check api"
```

---

### Task 9: Update SOP Routes To Remove Run Endpoints

**Files:**
- Modify: `app/api/v1/sop.py`
- Modify: `tests/test_sop_api.py`

**Step 1: Write failing route tests**

In `tests/test_sop_api.py`, keep only environment and SOP preview tests:

```python
@pytest.mark.asyncio
async def test_sop_run_routes_are_removed() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/sop/release-checklist/runs?env=dev")

    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_sop_api.py::test_sop_run_routes_are_removed -q
```

Expected: FAIL because old route still exists.

**Step 3: Remove old run endpoints from SOP router**

Modify `app/api/v1/sop.py`:

- Remove import of `BackgroundTasks`, `Request`, `JSONResponse`.
- Remove import of `run_sop_quality_graph_with_new_session`.
- Remove `RunRepositoryDep`, `SessionDep`, `run_to_summary`, `RunStartResponse`, `RunSummary`, and `SopQualityService`.
- Delete `POST /{sop_id}/runs`.
- Delete `GET /recent/runs`.
- Delete `GET /{sop_id}/runs`.
- Keep `GET /environments` and `GET /{sop_id}`.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_sop_api.py tests/test_sop_quality_checks_api.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/v1/sop.py tests/test_sop_api.py
git commit -m "refactor: remove sop run endpoints"
```

---

### Task 10: Delete Generic Runs And Agent Test-Run Coupling

**Files:**
- Delete: `app/models/runs.py`
- Delete: `app/repositories/runs.py`
- Delete: `app/schemas/runs.py`
- Delete: `app/api/v1/runs.py`
- Delete: `app/api/v1/run_views.py`
- Delete: `app/core/agent_streaming.py` if only used by old ReAct test runs
- Delete or simplify: `app/core/agent_runtime.py` if only used by old ReAct test runs
- Modify: `app/api/deps.py`
- Modify: `app/api/v1/agents.py`
- Modify: `app/services/agents.py`
- Modify: `api/openapi.yml`
- Delete/replace: `tests/test_runs_api.py`
- Delete/replace: `tests/test_run_repository.py`
- Delete/replace: `tests/test_run_views.py`
- Delete/replace: `tests/test_run_events.py`
- Delete/replace: `tests/test_schemas.py` run assertions
- Delete/replace: `tests/test_agent_test_runs.py`
- Delete/replace: `tests/test_agent_test_run_executor.py`
- Modify: `tests/test_openapi_contract.py`
- Modify: `README.md`

**Step 1: Write failing negative tests**

Add to `tests/test_openapi_contract.py`:

```python
def test_openapi_does_not_document_generic_runs() -> None:
    paths = load_contract()["paths"]

    assert not any(path.startswith("/api/runs") for path in paths)
    assert "/api/agents/{agent_key}/test-runs" not in paths
```

Add an API smoke test if desired:

```python
@pytest.mark.asyncio
async def test_generic_run_api_is_removed() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/runs/{uuid4()}")

    assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_openapi_contract.py::test_openapi_does_not_document_generic_runs -q
```

Expected: FAIL because old paths remain in `api/openapi.yml`.

**Step 3: Remove backend code**

Run:

```bash
git rm app/models/runs.py app/repositories/runs.py app/schemas/runs.py app/api/v1/runs.py app/api/v1/run_views.py
```

Remove `RunRepository` imports/dependencies from `app/api/deps.py`.

Modify `app/main.py` so it no longer imports or includes `runs`.

**Step 4: Remove agent test-run path**

Modify `app/api/v1/agents.py`:

- Remove `BackgroundTasks`, `Request`, and `JSONResponse` imports if only used for test-runs.
- Remove `RunRepositoryDep`.
- Remove `AgentTestRunCreate` and `RunStartResponse` imports.
- Delete `@router.post("/{agent_key}/test-runs")`.
- Keep agent create/list/draft/publish/version/delete endpoints.

Modify `app/services/agents.py`:

- Remove `RunRepository`, `AgentRuntime`, `consume_runtime_stream`, `open_postgres_checkpointer`, and run-related dataclasses/functions.
- Remove `start_test_run`, `run_agent_test`, and `run_agent_test_with_new_session`.
- Keep agent definition lifecycle methods.

Modify `app/schemas/agents.py` only if `AgentTestRunCreate` becomes unused. If there is no product use, remove `AgentMessage` and `AgentTestRunCreate`; otherwise leave them until a future graph-task redesign.

**Step 5: Update tests**

Delete old tests that only covered generic run storage or agent test runs:

```bash
git rm tests/test_runs_api.py tests/test_run_repository.py tests/test_run_views.py tests/test_run_events.py tests/test_agent_test_runs.py tests/test_agent_test_run_executor.py
```

Update:

- `tests/test_models.py` to remove `Run`/`RunEvent` imports.
- `tests/test_api_dependencies.py` to assert `SopQualityCheckRepositoryDep`, not `RunRepositoryDep`.
- `tests/test_openapi_contract.py` to remove agent test-run expectations and add SOP quality check expectations.
- Any remaining imports found by `rg -n "RunRepository|RunStatus|RunStartResponse|/api/runs|test-runs|run_events|runs" app tests api`.

**Step 6: Update OpenAPI contract**

Modify `api/openapi.yml`:

- Remove `/api/runs/{run_id}`.
- Remove `/api/runs/{run_id}/events`.
- Remove `/api/sop/{sop_id}/runs`.
- Remove `/api/sop/recent/runs`.
- Remove `/api/agents/{agent_key}/test-runs`.
- Add `/api/sop-quality-checks`.
- Add `/api/sop-quality-checks/{check_id}`.
- Add `/api/sop-quality-checks/{check_id}/events`.
- Add `/api/sop-quality-checks/{check_id}/stream`.
- Add schemas matching `SopQualityCheckStartResponse`, `SopQualityCheckSummary`, `SopQualityCheckDetail`, `SopQualityDisplayState`, and `SopQualityCheckEvent`.

**Step 7: Update docs/scripts**

Modify `README.md`:

- Replace "runs" language with "SOP quality checks".
- Mention LangGraph Postgres checkpoints as graph state storage.
- Update debugging URLs to `/api/sop-quality-checks`.

Delete `scripts/seed_mock_runs.py` or replace it with `scripts/seed_mock_sop_quality_checks.py` only if the script is still useful.

**Step 8: Run tests**

Run:

```bash
uv run pytest tests/test_openapi_contract.py tests/test_api_dependencies.py tests/test_models.py tests/test_agent_service.py tests/test_agents_api.py -q
```

Expected: PASS.

Run a repository-wide search:

```bash
rg -n "RunRepository|RunStatus|RunStartResponse|/api/runs|run_events|runs" app tests api README.md scripts || true
```

Expected: no old generic run references except historical prose in design/plan docs.

**Step 9: Commit**

```bash
git add app tests api README.md scripts
git commit -m "refactor: remove generic run execution path"
```

---

### Task 11: Frontend API, Types, Reducer, And Hooks

**Files:**
- Create: `frontend/src/features/sop-quality-checks/types.ts`
- Create: `frontend/src/features/sop-quality-checks/api.ts`
- Create: `frontend/src/features/sop-quality-checks/reducer.ts`
- Create: `frontend/src/features/sop-quality-checks/hooks.ts`
- Create: `frontend/src/features/sop-quality-checks/api.test.ts`
- Create: `frontend/src/features/sop-quality-checks/reducer.test.ts`
- Create: `frontend/src/features/sop-quality-checks/hooks.test.tsx`
- Modify: `frontend/src/lib/sse.ts`

**Step 1: Write failing API tests**

Create `frontend/src/features/sop-quality-checks/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildSopQualityCheckStreamUrl,
  startSopQualityCheck,
} from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("sop quality checks API", () => {
  it("maps a newly created check", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          check_id: "check-1",
          status: "pending",
          created: true,
          status_url: "/api/sop-quality-checks/check-1",
          stream_url: "/api/sop-quality-checks/check-1/stream",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(startSopQualityCheck("release-checklist", "dev")).resolves.toEqual({
      kind: "created",
      checkId: "check-1",
    });
  });

  it("maps an existing active check", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          check_id: "check-1",
          status: "running",
          created: false,
          status_url: "/api/sop-quality-checks/check-1",
          stream_url: "/api/sop-quality-checks/check-1/stream",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(startSopQualityCheck("release-checklist", "dev")).resolves.toEqual({
      kind: "active",
      checkId: "check-1",
    });
  });

  it("builds stream URLs with a sequence cursor", () => {
    expect(buildSopQualityCheckStreamUrl("check-1", 12)).toBe(
      "/api/sop-quality-checks/check-1/stream?after=12",
    );
  });
});
```

**Step 2: Write failing reducer tests**

Create `frontend/src/features/sop-quality-checks/reducer.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  createInitialSopQualityCheckViewState,
  reduceSopQualityCheckEvent,
} from "./reducer";

describe("sop quality check reducer", () => {
  it("tracks lifecycle event sequence without payload", () => {
    const state = reduceSopQualityCheckEvent(
      createInitialSopQualityCheckViewState(),
      {
        check_id: "check-1",
        sequence: 2,
        type: "checkpoint",
        node: "check_steps",
        checkpoint_id: "checkpoint-1",
        task_id: null,
        message: "Checkpoint saved.",
      },
    );

    expect(state.latestSequence).toBe(2);
    expect(state.needsRefresh).toBe(true);
  });
});
```

**Step 3: Run tests to verify they fail**

Run:

```bash
cd frontend
npm run test -- --run src/features/sop-quality-checks/api.test.ts src/features/sop-quality-checks/reducer.test.ts
```

Expected: FAIL with missing modules.

**Step 4: Implement types and API**

Create `frontend/src/features/sop-quality-checks/types.ts`:

```ts
export type SopQualityCheckStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "interrupted";

export type SopQualityNodeState = {
  status: "idle" | "running" | "done" | "error" | "interrupted";
  streamText: string;
  error?: string;
};

export type SopQualityDisplayState = {
  latest_sequence: number;
  nodes: Record<string, SopQualityNodeState>;
  is_running: boolean;
};

export type SopQualityCheckDetail = {
  check_id: string;
  sop_id: string;
  env_key: string;
  status: SopQualityCheckStatus;
  quality_result?: string | null;
  latest_sequence: number;
  current_checkpoint_id?: string | null;
  result?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  display_state: SopQualityDisplayState;
};

export type SopQualityCheckEvent = {
  check_id: string;
  sequence: number;
  type: "created" | "started" | "checkpoint" | "completed" | "failed" | "interrupted";
  node?: string | null;
  checkpoint_id?: string | null;
  task_id?: string | null;
  message?: string | null;
};

export type StartSopQualityCheckResult =
  | { kind: "created"; checkId: string }
  | { kind: "active"; checkId: string };
```

Create `frontend/src/features/sop-quality-checks/api.ts`:

```ts
import { apiErrorFromResponse, requestJson } from "../../lib/apiClient";
import type {
  SopQualityCheckDetail,
  StartSopQualityCheckResult,
} from "./types";

type StartResponse = {
  check_id?: string;
  created?: boolean;
};

export async function startSopQualityCheck(
  sopId: string,
  envKey: string,
): Promise<StartSopQualityCheckResult> {
  const response = await fetch(
    `/api/sop-quality-checks?sop_id=${encodeURIComponent(sopId)}&env=${encodeURIComponent(envKey)}`,
    { method: "POST", headers: { Accept: "application/json" } },
  );

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  const body = (await response.json()) as StartResponse;
  if (!body.check_id) {
    throw new Error("SOP quality check response did not include a check id.");
  }

  return {
    kind: body.created ? "created" : "active",
    checkId: body.check_id,
  };
}

export function getSopQualityCheck(checkId: string): Promise<SopQualityCheckDetail> {
  return requestJson<SopQualityCheckDetail>(
    `/api/sop-quality-checks/${encodeURIComponent(checkId)}`,
  );
}

export function buildSopQualityCheckStreamUrl(checkId: string, after = 0): string {
  return `/api/sop-quality-checks/${encodeURIComponent(checkId)}/stream?after=${after}`;
}
```

**Step 5: Implement reducer and hooks**

Create `frontend/src/features/sop-quality-checks/reducer.ts` with:

- `createInitialSopQualityCheckViewState()`.
- `hydrateFromDisplayState(displayState)`.
- `reduceSopQualityCheckEvent(state, event)`.

For a `checkpoint` event, set `needsRefresh: true`. For `completed`, `failed`, and `interrupted`, set `isRunning: false` and `connectionStatus: "closed"`.

Create `frontend/src/features/sop-quality-checks/hooks.ts`:

- `useSopQualityCheck(checkId: string)`.
- Fetch detail first.
- Hydrate reducer from `detail.display_state`.
- Connect to `buildSopQualityCheckStreamUrl(checkId, latestSequence)`.
- On `checkpoint`, refresh detail.
- Ignore stale detail/events when `checkId` changes.

Use the existing `frontend/src/features/runs/hooks.ts` stale-response and reconnect patterns, but do not import the old `runs` feature.

**Step 6: Run frontend feature tests**

Run:

```bash
cd frontend
npm run test -- --run src/features/sop-quality-checks
```

Expected: PASS.

**Step 7: Commit**

```bash
git add frontend/src/features/sop-quality-checks frontend/src/lib/sse.ts
git commit -m "feat: add sop quality check frontend state"
```

---

### Task 12: Frontend SOP Page And Sidebar Adaptation

**Files:**
- Create: `frontend/src/features/sop-quality-checks/components/SopQualityCheckObserver.tsx`
- Modify: `frontend/src/features/sop/pages/ChatPage.tsx`
- Modify: `frontend/src/features/sop/api.ts`
- Modify: `frontend/src/features/sop/hooks.ts`
- Modify: `frontend/src/features/sop/types.ts`
- Modify: `frontend/src/app/RecentSopSidebarPanel.tsx`
- Modify: `frontend/src/app/WorkspaceLayoutContext.tsx` only if naming needs to change
- Delete: `frontend/src/features/runs/*` after no imports remain
- Modify tests under `frontend/src/features/sop/` and `frontend/src/app/`

**Step 1: Write failing page tests**

Update `frontend/src/features/sop/pages/ChatPage.test.tsx` expectations:

```ts
expect(fetch).toHaveBeenCalledWith(
  "/api/sop-quality-checks?sop_id=release-checklist&env=dev",
  expect.objectContaining({ method: "POST" }),
);
expect(mockNavigate).toHaveBeenCalledWith("/sop?checkId=check-1", { replace: true });
```

Add a test that route `?checkId=check-1` renders `SopQualityCheckObserver`.

Update `frontend/src/app/WorkspaceSidebar.test.tsx` or `RecentSopSidebarPanel` tests to expect navigation to `/sop?checkId=<id>`.

**Step 2: Run tests to verify they fail**

Run:

```bash
cd frontend
npm run test -- --run src/features/sop/pages/ChatPage.test.tsx src/app/WorkspaceSidebar.test.tsx
```

Expected: FAIL because current code still uses `runId`.

**Step 3: Implement observer**

Create `frontend/src/features/sop-quality-checks/components/SopQualityCheckObserver.tsx`:

```tsx
import { useEffect, useRef } from "react";

import { useSopQualityCheck } from "../hooks";

type Props = {
  checkId: string;
  registeredNodeIds?: string[];
};

const DEFAULT_REGISTERED_NODE_IDS = ["load_sop", "check_steps", "summarize_result"];

export function SopQualityCheckObserver({
  checkId,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: Props) {
  const { detail, error, loading, state } = useSopQualityCheck(checkId);

  if (error) {
    return <section role="alert" className="rounded-2xl border border-error-soft bg-canvas px-4 py-3 text-sm text-error-deep">{error.message}</section>;
  }

  if (!detail) {
    return <section className="rounded-2xl border border-hairline bg-canvas px-4 py-3 text-sm text-body">{loading ? "Loading check..." : "Check not found."}</section>;
  }

  return (
    <section aria-label="SOP quality check observer" className="flex flex-col gap-4 text-ink">
      <div className="flex justify-end">
        <p className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-3xl bg-primary px-4 py-2 text-sm text-on-primary shadow-sm">
          {`Please run a quality check for SOP \`${detail.sop_id}\`.`}
        </p>
      </div>
      <ObserverTurns
        nodes={state.nodes}
        registeredNodeIds={registeredNodeIds}
        isRunning={state.isRunning}
      />
      <ObserverFootnote status={detail.status} connectionStatus={state.connectionStatus} />
      <AutoScrollMarker dependency={state.latestSequence} />
    </section>
  );
}
```

Reuse the presentational pieces from `RunObserver.tsx` initially by moving generic UI helpers into this file. Keep class names/design tokens consistent with current UI.

**Step 4: Update ChatPage**

Modify `frontend/src/features/sop/pages/ChatPage.tsx`:

- Replace `RunObserver` import with `SopQualityCheckObserver`.
- Replace `startSopQualityRun` with `startSopQualityCheck`.
- Rename state from `observedRunId` to `observedCheckId`.
- Read `const routeCheckId = searchParams.get("checkId")`.
- Navigate to `/sop?checkId=${result.checkId}`.
- Active message: `已存在进行中的质检，已加入检查 ${result.checkId}。`
- Rename `RunCanvas` to `CheckCanvas`.

**Step 5: Update SOP history APIs**

Modify `frontend/src/features/sop/types.ts` to remove `RunStatus` import and define check history:

```ts
export type SopQualityCheckHistoryItem = {
  check_id: string;
  sop_id?: string | null;
  env_key?: string | null;
  status?: string | null;
  created_at?: string | null;
};
```

Modify `frontend/src/features/sop/api.ts`:

- Remove `startSopQualityRun`.
- Add `getSopQualityCheckHistory(sopId, envKey)`.
- Add `getRecentSopQualityChecks(envKey, limit)`.
- Use `/api/sop-quality-checks?sop_id=&env=&limit=`.

Modify `frontend/src/features/sop/hooks.ts` to call the new history API names.

**Step 6: Update sidebar**

Modify `frontend/src/app/RecentSopSidebarPanel.tsx`:

- Read `activeCheckId = new URLSearchParams(location.search).get("checkId")`.
- Navigate to `/sop?checkId=${check.check_id}`.
- Rename local variables from `run` to `check`.
- Keep the current compact sidebar UI and design tokens.

**Step 7: Delete old frontend runs feature**

After `rg -n "features/runs|RunObserver|runId|startSopQualityRun" frontend/src` shows no product imports, remove:

```bash
git rm -r frontend/src/features/runs
```

If tests still import old run helpers, replace them with `sop-quality-checks` tests from Task 11.

**Step 8: Run frontend tests**

Run:

```bash
cd frontend
npm run test -- --run src/features/sop src/features/sop-quality-checks src/app
```

Expected: PASS.

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

**Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat: adapt sop frontend to quality checks"
```

---

### Task 13: Contract, Documentation, And End-To-End Verification

**Files:**
- Modify: `api/openapi.yml`
- Modify: `README.md`
- Modify: `frontend/README.md`
- Modify: `docs/plans/2026-05-28-sop-quality-checkpoint-design.md` only if implementation uncovered a required correction

**Step 1: Write or update contract tests**

In `tests/test_openapi_contract.py`, add:

```python
def test_sop_quality_check_paths_are_documented() -> None:
    contract = load_contract()
    paths = contract["paths"]

    expected = {
        ("/api/sop-quality-checks", "post"): {"200", "202", "401", "404", "422", "502"},
        ("/api/sop-quality-checks", "get"): {"200", "401", "422"},
        ("/api/sop-quality-checks/{check_id}", "get"): {"200", "401", "404", "422"},
        ("/api/sop-quality-checks/{check_id}/events", "get"): {"200", "401", "404", "422"},
        ("/api/sop-quality-checks/{check_id}/stream", "get"): {"200", "401", "404", "422"},
    }

    for (path, method), statuses in expected.items():
        operation = paths[path][method]
        assert operation["tags"] == ["sop-quality-checks"]
        assert statuses <= set(operation["responses"])

    schemas = contract["components"]["schemas"]
    assert "SopQualityCheckStartResponse" in schemas
    assert "SopQualityCheckEvent" in schemas
    assert "payload" not in schemas["SopQualityCheckEvent"]["properties"]
```

**Step 2: Run contract tests to verify they fail before OpenAPI update**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -q
```

Expected: FAIL until `api/openapi.yml` is updated.

**Step 3: Update docs**

Update `README.md` and `frontend/README.md`:

- Replace "SOP runs" with "SOP quality checks".
- Document `POST /api/sop-quality-checks?sop_id=&env=`.
- Document `GET /api/sop-quality-checks/{check_id}/stream?after=`.
- State that LangGraph checkpoints store graph state and `sop_quality_events` only stores lightweight reconnect cursors.

**Step 4: Run full backend verification**

Run:

```bash
uv run pytest
```

Expected: PASS, with DB-marked tests skipped if `TEST_DATABASE_URL` is unset.

If Postgres 13 is available, also run:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent_test uv run pytest -m db
```

Expected: PASS.

**Step 5: Run full frontend verification**

Run:

```bash
cd frontend
npm run test
npm run build
```

Expected: PASS.

**Step 6: Run stale-reference scan**

Run:

```bash
rg -n "runId|RunObserver|startSopQualityRun|/api/runs|run_events|RunRepository|RunStatus|RunStartResponse|agent_test_run|test-runs" app tests api frontend/src README.md frontend/README.md || true
```

Expected: no active product/test references. References inside historical design or implementation plan docs are acceptable.

**Step 7: Commit**

```bash
git add api/openapi.yml README.md frontend/README.md tests/test_openapi_contract.py docs/plans/2026-05-28-sop-quality-checkpoint-design.md
git commit -m "docs: document sop quality check api"
```

---

### Task 14: Manual Smoke Test

**Files:**
- Modify: none unless bugs are found

**Step 1: Start Postgres 13**

Run:

```bash
docker run -d --name cqa-postgres-13 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=change_quality_agent \
  -p 5432:5432 \
  postgres:13
```

If the container already exists, start it:

```bash
docker start cqa-postgres-13
```

**Step 2: Run migrations**

Run:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run alembic upgrade head
```

Expected: migrations apply through `20260527_0004`.

**Step 3: Start backend**

Run:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
AUTH_DEV_MODE=true \
make dev
```

Expected: FastAPI listening on `http://127.0.0.1:8000`.

**Step 4: Start frontend**

Run in another terminal:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Expected: Vite listening on `http://127.0.0.1:5173`.

**Step 5: Verify first user flow**

Open `http://127.0.0.1:5173/sop`.

Actions:

1. Select `dev`.
2. Enter `release-checklist`.
3. Click start quality check.

Expected:

- URL becomes `/sop?checkId=<uuid>`.
- The page shows SOP quality output.
- Network tab shows `POST /api/sop-quality-checks` returning `202`.
- Network tab shows SSE connection to `/api/sop-quality-checks/<uuid>/stream?after=...`.

**Step 6: Verify second user join flow**

Open a second browser context or incognito window and repeat the same SOP/env start.

Expected:

- `POST /api/sop-quality-checks` returns `200`.
- The returned `check_id` is the same as the first user.
- The UI navigates to the same `/sop?checkId=<uuid>`.
- Prior display state is visible and subsequent stream events appear.

**Step 7: Final commit if smoke fixes were needed**

Only if fixes were made:

```bash
git add <fixed-files>
git commit -m "fix: polish sop quality check smoke flow"
```

---

## Final Verification Checklist

Run before opening a PR or asking for review:

```bash
git status --short
uv run pytest
cd frontend && npm run test && npm run build
```

Expected:

- `git status --short` shows only intentional committed work or is clean.
- Backend tests pass.
- Frontend tests pass.
- Frontend build passes.
- `rg` stale-reference scan has no active old run references.


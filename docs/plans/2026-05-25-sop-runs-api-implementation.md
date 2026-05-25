# SOP Runs API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the SOP run API substrate with mocked SOP fetching, Postgres-backed run history, persisted events, duplicate active-run rejection, and SSE observation.

**Architecture:** FastAPI exposes SOP entry APIs and generic run observation APIs. A service layer owns scheduling and execution orchestration, Postgres stores business `runs` and `run_events`, and LangGraph runs in-process for v1 with official checkpoint storage kept separate. The SOP client is an interface with a mock implementation until the real client is provided later.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, asyncpg, Alembic, pytest, httpx, LangGraph, langgraph-checkpoint-postgres, Postgres 13.22.

---

### Task 1: Add Runtime and Test Dependencies

**Files:**
- Modify: `pyproject.toml`
- Verify: `uv.lock`

**Step 1: Add dependencies**

Run:

```bash
uv add "sqlalchemy>=2.0" asyncpg alembic pydantic-settings langgraph-checkpoint-postgres
uv add --dev pytest pytest-asyncio httpx
```

Expected: dependencies are added to `pyproject.toml` and `uv.lock`.

**Step 2: Verify dependency metadata**

Run:

```bash
uv lock --check
```

Expected: PASS with lockfile in sync.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add API persistence dependencies"
```

### Task 2: Scaffold the FastAPI Project Layout

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/api/__init__.py`
- Create: `app/api/deps.py`
- Create: `app/api/v1/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/config.py`
- Create: `app/core/database.py`
- Create: `app/schemas/__init__.py`
- Modify: `pyproject.toml`
- Test: `tests/test_app.py`

**Step 1: Write the failing test**

Create `tests/test_app.py`:

```python
from httpx import ASGITransport, AsyncClient
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_check() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_app.py::test_health_check -v
```

Expected: FAIL because `app.main` does not exist.

**Step 3: Write minimal implementation**

Create `app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Change Quality Agent")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

Create empty `__init__.py` files for all packages listed above.

Modify `pyproject.toml`:

```toml
[tool.fastapi]
entrypoint = "app.main:app"
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_app.py::test_health_check -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app tests/test_app.py pyproject.toml
git commit -m "feat: scaffold FastAPI application"
```

### Task 3: Add Environment Configuration

**Files:**
- Modify: `app/core/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
import pytest

from app.core.config import EnvironmentConfig, Settings


def test_environment_lookup_by_key() -> None:
    settings = Settings(
        environments=[
            EnvironmentConfig(
                key="dev",
                name_zh="开发",
                name_en="Development",
                sop_client_options={"base_url": "https://dev.example.test"},
            )
        ]
    )

    env = settings.get_environment("dev")

    assert env.key == "dev"
    assert env.public_dict() == {
        "key": "dev",
        "name_zh": "开发",
        "name_en": "Development",
    }


def test_unknown_environment_raises_key_error() -> None:
    settings = Settings(environments=[])

    with pytest.raises(KeyError):
        settings.get_environment("prod")
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL because configuration models do not exist.

**Step 3: Implement configuration models**

In `app/core/config.py`:

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentConfig(BaseModel):
    key: str
    name_zh: str
    name_en: str
    sop_client_options: dict[str, str] = Field(default_factory=dict)

    def public_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "name_zh": self.name_zh,
            "name_en": self.name_en,
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent"
    environments: list[EnvironmentConfig] = Field(
        default_factory=lambda: [
            EnvironmentConfig(
                key="dev",
                name_zh="开发",
                name_en="Development",
                sop_client_options={},
            )
        ]
    )

    def get_environment(self, key: str) -> EnvironmentConfig:
        for environment in self.environments:
            if environment.key == key:
                return environment
        raise KeyError(key)


settings = Settings()
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/core/config.py tests/test_config.py
git commit -m "feat: add environment configuration"
```

### Task 4: Define Run and SOP Schemas

**Files:**
- Create: `app/schemas/runs.py`
- Create: `app/schemas/sop.py`
- Test: `tests/test_schemas.py`

**Step 1: Write the failing tests**

Create `tests/test_schemas.py`:

```python
from uuid import uuid4

from app.schemas.runs import RunStatus, RunSummary
from app.schemas.sop import SopSnapshot


def test_run_status_uses_official_values() -> None:
    assert {status.value for status in RunStatus} == {
        "pending",
        "running",
        "success",
        "error",
        "timeout",
        "interrupted",
    }


def test_run_summary_exposes_stable_projection() -> None:
    run_id = uuid4()
    summary = RunSummary(
        run_id=run_id,
        subject_type="sop",
        subject_id="release-checklist",
        status=RunStatus.running,
        current_node="load_sop",
        completed_nodes=[],
        latest_sequence=1,
    )

    assert summary.run_id == run_id
    assert summary.status == RunStatus.running


def test_sop_snapshot_accepts_raw_payload() -> None:
    snapshot = SopSnapshot(
        sop_id="release-checklist",
        env_key="dev",
        source_version="v1",
        updated_at=None,
        payload={"steps": ["review", "deploy"]},
    )

    assert snapshot.payload["steps"] == ["review", "deploy"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_schemas.py -v
```

Expected: FAIL because schema modules do not exist.

**Step 3: Implement schemas**

In `app/schemas/runs.py`:

```python
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    error = "error"
    timeout = "timeout"
    interrupted = "interrupted"


class RunStartResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    status_url: str
    events_url: str


class ActiveRunConflict(BaseModel):
    message: str
    active_run_id: UUID
    status_url: str
    events_url: str


class RunSummary(BaseModel):
    run_id: UUID
    subject_type: str
    subject_id: str
    status: RunStatus
    current_node: str | None = None
    completed_nodes: list[str]
    latest_sequence: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_status: str | None = None
    error_summary: str | None = None


class RunDebug(BaseModel):
    thread_id: str
    current_checkpoint_id: str | None = None
    langgraph_state_snapshot: dict[str, Any] | None = None
    raw_graph_output: dict[str, Any] | None = None
    raw_last_event: dict[str, Any] | None = None


class RunDetail(RunSummary):
    debug: RunDebug | None = None
```

In `app/schemas/sop.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EnvironmentPublic(BaseModel):
    key: str
    name_zh: str
    name_en: str


class SopSnapshot(BaseModel):
    sop_id: str
    env_key: str
    source_version: str | None = None
    updated_at: datetime | None = None
    payload: dict[str, Any]
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_schemas.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/schemas tests/test_schemas.py
git commit -m "feat: add SOP run schemas"
```

### Task 5: Add Mock SOP Client

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/sop_client.py`
- Test: `tests/test_sop_client.py`

**Step 1: Write the failing tests**

Create `tests/test_sop_client.py`:

```python
import pytest

from app.services.sop_client import MockSopClient, SopNotFoundError


@pytest.mark.asyncio
async def test_mock_sop_client_returns_snapshot() -> None:
    client = MockSopClient()

    snapshot = await client.get_sop("release-checklist", "dev")

    assert snapshot.sop_id == "release-checklist"
    assert snapshot.env_key == "dev"
    assert snapshot.payload["title"] == "Mock SOP release-checklist"


@pytest.mark.asyncio
async def test_mock_sop_client_can_simulate_not_found() -> None:
    client = MockSopClient(missing_sop_ids={"missing"})

    with pytest.raises(SopNotFoundError):
        await client.get_sop("missing", "dev")
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_sop_client.py -v
```

Expected: FAIL because `app.services.sop_client` does not exist.

**Step 3: Implement mock client**

Create `app/services/sop_client.py`:

```python
from typing import Protocol

from app.schemas.sop import SopSnapshot


class SopNotFoundError(Exception):
    pass


class SopClientError(Exception):
    pass


class SopClient(Protocol):
    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        ...


class MockSopClient:
    def __init__(self, missing_sop_ids: set[str] | None = None) -> None:
        self._missing_sop_ids = missing_sop_ids or set()

    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        if sop_id in self._missing_sop_ids:
            raise SopNotFoundError(sop_id)
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="mock-v1",
            updated_at=None,
            payload={
                "id": sop_id,
                "title": f"Mock SOP {sop_id}",
                "env": env_key,
                "steps": [
                    {"id": "prepare", "title": "Prepare change"},
                    {"id": "review", "title": "Review change"},
                    {"id": "execute", "title": "Execute change"},
                ],
            },
        )
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_sop_client.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/services tests/test_sop_client.py
git commit -m "feat: add mock SOP client"
```

### Task 6: Add Database Engine and ORM Models

**Files:**
- Modify: `app/core/database.py`
- Create: `app/models/__init__.py`
- Create: `app/models/runs.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing tests**

Create `tests/test_models.py`:

```python
from app.models.runs import Run, RunEvent


def test_run_model_table_name() -> None:
    assert Run.__tablename__ == "runs"


def test_run_event_model_table_name() -> None:
    assert RunEvent.__tablename__ == "run_events"
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL because models do not exist.

**Step 3: Implement database and models**

In `app/core/database.py`:

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session
```

In `app/models/runs.py`, define `Run` and `RunEvent` with SQLAlchemy 2 typed
mappings for all fields in the design document. Use `JSON` for JSONB-compatible
model typing and make Alembic render the actual Postgres `JSONB` type in the
migration.

Minimum class skeleton:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index(
            "uq_runs_active_conflict_key",
            "active_conflict_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_conflict_key: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    kwargs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    current_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    current_node: Mapped[str | None] = mapped_column(Text)
    completed_nodes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    subject_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_status: Mapped[str | None] = mapped_column(Text)
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_graph_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["RunEvent"]] = relationship(back_populates="run")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        Index("uq_run_events_run_sequence", "run_id", "sequence", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    node: Mapped[str | None] = mapped_column(Text)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_id: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[Run] = relationship(back_populates="events")
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_models.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/core/database.py app/models tests/test_models.py
git commit -m "feat: add run persistence models"
```

### Task 7: Add Alembic Migration

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/20260525_0001_create_runs.py`

**Step 1: Initialize migration files**

Run:

```bash
uv run alembic init migrations
```

Expected: Alembic creates migration scaffolding.

**Step 2: Wire metadata and database URL**

Modify `migrations/env.py` to import:

```python
from app.core.config import settings
from app.core.database import Base
from app.models import runs
```

Set `target_metadata = Base.metadata` and use `settings.database_url`.

**Step 3: Create the migration**

Run:

```bash
uv run alembic revision --autogenerate -m "create runs"
```

Expected: migration includes `runs`, `run_events`, and both unique indexes.

**Step 4: Review migration**

Confirm the active conflict index uses:

```python
postgresql_where=sa.text("status IN ('pending', 'running')")
```

Confirm `metadata` is rendered as a column name even though the ORM attribute is
`metadata_`.

**Step 5: Commit**

```bash
git add alembic.ini migrations
git commit -m "feat: add run persistence migration"
```

### Task 8: Add Run Repository

**Files:**
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/runs.py`
- Test: `tests/test_run_repository.py`

**Step 1: Write repository tests**

Use an async SQLAlchemy test session. If a Postgres test database is not
available locally, mark repository integration tests with `pytest.mark.db` and
document `TEST_DATABASE_URL`.

Create tests for:

```python
async def test_create_run_persists_sop_metadata(session):
    ...


async def test_active_conflict_key_rejects_duplicate_active_run(session):
    ...


async def test_terminal_run_does_not_block_new_run(session):
    ...


async def test_append_event_increments_sequence(session):
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent_test uv run pytest tests/test_run_repository.py -v
```

Expected: FAIL until repository exists and test database is prepared.

**Step 3: Implement repository**

Create repository methods:

```python
class ActiveRunExistsError(Exception):
    def __init__(self, active_run_id: UUID) -> None:
        self.active_run_id = active_run_id


class RunRepository:
    async def create_sop_run(...): ...
    async def get_run(...): ...
    async def list_sop_runs(...): ...
    async def mark_running(...): ...
    async def mark_terminal(...): ...
    async def append_event(...): ...
    async def get_events_after(...): ...
    async def interrupt_active_runs_on_startup(...): ...
```

On unique constraint violation for `uq_runs_active_conflict_key`, query the
active run by conflict key and raise `ActiveRunExistsError`.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS with Postgres 13.22 or a compatible local Postgres.

**Step 5: Commit**

```bash
git add app/repositories tests/test_run_repository.py
git commit -m "feat: add run repository"
```

### Task 9: Add Event Envelope Adapter

**Files:**
- Create: `app/services/run_events.py`
- Test: `tests/test_run_events.py`

**Step 1: Write the failing tests**

Create tests for:

```python
def test_message_event_extracts_node_from_metadata():
    ...


def test_update_event_extracts_node_from_chunk_key():
    ...


def test_error_event_preserves_run_and_sequence():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_run_events.py -v
```

Expected: FAIL because adapter does not exist.

**Step 3: Implement adapter**

Expose functions such as:

```python
def normalize_langgraph_chunk(
    *,
    chunk_type: str,
    chunk: object,
    run_id: str,
    thread_id: str,
    sequence: int,
) -> dict[str, object]:
    ...
```

Support `tasks`, `messages`, `updates`, `custom`, `checkpoints`, `error`, and
`done`. Preserve raw chunk content under `payload["raw"]` where useful, but keep
stable top-level fields available for clients.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_run_events.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/services/run_events.py tests/test_run_events.py
git commit -m "feat: normalize LangGraph run events"
```

### Task 10: Add SOP Run Scheduling Service

**Files:**
- Create: `app/services/sop_quality.py`
- Test: `tests/test_sop_quality_service.py`

**Step 1: Write the failing tests**

Create tests with fake repository and mock SOP client:

```python
async def test_start_sop_run_fetches_sop_before_creating_run():
    ...


async def test_start_sop_run_returns_conflict_for_active_run():
    ...


async def test_start_sop_run_builds_conflict_key():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_sop_quality_service.py -v
```

Expected: FAIL because service does not exist.

**Step 3: Implement scheduling service**

Create:

```python
class SopQualityService:
    async def start_run(self, sop_id: str, env_key: str, created_by: str | None = None) -> RunStartResult:
        ...
```

Responsibilities:

- Validate environment key through settings.
- Fetch SOP through the injected `SopClient` before creating a run.
- Build `active_conflict_key = f"sop:{sop_id}:env:{env_key}"`.
- Persist `subject_snapshot`, `env_snapshot`, `metadata`, and `kwargs`.
- Return conflict details when repository raises `ActiveRunExistsError`.
- Schedule graph execution only after the DB transaction has committed.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_sop_quality_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/services/sop_quality.py tests/test_sop_quality_service.py
git commit -m "feat: add SOP run scheduler"
```

### Task 11: Add Minimal In-Process Graph Runner

**Files:**
- Create: `agent/__init__.py`
- Create: `agent/state.py`
- Create: `agent/graph.py`
- Modify: `app/services/sop_quality.py`
- Test: `tests/test_graph_runner.py`

**Step 1: Write the failing test**

Create a test that runs a tiny graph against a fake repository:

```python
async def test_graph_runner_writes_done_event():
    ...
```

Assert the service marks the run `running`, appends at least one `custom` or
`updates` event, stores `raw_graph_output`, and marks the run `success`.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_graph_runner.py -v
```

Expected: FAIL because graph runner does not exist.

**Step 3: Implement minimal graph**

Use a small placeholder LangGraph workflow that validates the stored SOP
snapshot and emits deterministic events. Do not implement final quality report
logic yet; store:

```python
structured_result = None
raw_graph_output = {"status": "mock_success"}
```

Keep the code shaped so real SOP quality nodes can replace the mock graph later.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_graph_runner.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent app/services/sop_quality.py tests/test_graph_runner.py
git commit -m "feat: add in-process SOP graph runner"
```

### Task 12: Wire API Dependencies

**Files:**
- Modify: `app/api/deps.py`
- Modify: `app/main.py`
- Test: `tests/test_api_dependencies.py`

**Step 1: Write dependency tests**

Create tests that override dependencies and assert:

```python
def test_sop_client_dependency_defaults_to_mock():
    ...


def test_run_repository_dependency_uses_session():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_api_dependencies.py -v
```

Expected: FAIL because dependencies are not wired.

**Step 3: Implement dependencies**

Use `Annotated` dependency aliases:

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.runs import RunRepository
from app.services.sop_client import MockSopClient, SopClient

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_sop_client() -> SopClient:
    return MockSopClient()


SopClientDep = Annotated[SopClient, Depends(get_sop_client)]


def get_run_repository(session: SessionDep) -> RunRepository:
    return RunRepository(session)


RunRepositoryDep = Annotated[RunRepository, Depends(get_run_repository)]
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_api_dependencies.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/deps.py app/main.py tests/test_api_dependencies.py
git commit -m "feat: wire API dependencies"
```

### Task 13: Add SOP APIs

**Files:**
- Create: `app/api/v1/sop.py`
- Modify: `app/main.py`
- Test: `tests/test_sop_api.py`

**Step 1: Write failing API tests**

Create tests for:

```python
async def test_list_environments():
    ...


async def test_get_sop_preview_does_not_create_run():
    ...


async def test_start_sop_run_returns_accepted():
    ...


async def test_start_sop_run_conflict_returns_409():
    ...


async def test_list_sop_run_history():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_sop_api.py -v
```

Expected: FAIL because router does not exist.

**Step 3: Implement router**

Use router-level metadata:

```python
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

router = APIRouter(prefix="/api/sop", tags=["sop"])
```

Implement:

- `GET /environments`
- `GET /{sop_id}`
- `POST /{sop_id}/runs`
- `GET /{sop_id}/runs`

Use `Annotated[str, Query()]` for the `env` query parameter.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_sop_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/v1/sop.py app/main.py tests/test_sop_api.py
git commit -m "feat: add SOP run APIs"
```

### Task 14: Add Generic Run APIs and SSE

**Files:**
- Create: `app/api/v1/runs.py`
- Modify: `app/main.py`
- Test: `tests/test_runs_api.py`

**Step 1: Write failing API tests**

Create tests for:

```python
async def test_get_run_returns_summary():
    ...


async def test_get_run_debug_includes_thread_fields():
    ...


async def test_events_replay_after_sequence():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_runs_api.py -v
```

Expected: FAIL because router does not exist.

**Step 3: Implement run router**

Use:

```python
from fastapi.responses import StreamingResponse
```

Implement:

- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events?after=0`

Format SSE frames:

```python
def format_sse(event: dict[str, object]) -> str:
    return f"id: {event['sequence']}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
```

For v1, use persisted DB replay plus a simple polling loop for new events.
Document that an in-process broadcast can be added later for lower latency.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_runs_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/v1/runs.py app/main.py tests/test_runs_api.py
git commit -m "feat: add generic run observation APIs"
```

### Task 15: Add Startup Cleanup for Interrupted Runs

**Files:**
- Modify: `app/main.py`
- Modify: `app/repositories/runs.py`
- Test: `tests/test_startup_cleanup.py`

**Step 1: Write the failing test**

Create a test that inserts `pending` and `running` runs, triggers the lifespan
startup cleanup function, and asserts both are marked `interrupted` with a
system event.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_startup_cleanup.py -v
```

Expected: FAIL until startup cleanup exists.

**Step 3: Implement startup cleanup**

Use FastAPI lifespan in `app/main.py`:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await interrupt_leftover_runs()
    yield
```

`interrupt_leftover_runs()` should mark active runs as `interrupted` and append
a `custom` or `error` system event explaining that service startup interrupted
the previous in-process execution.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_startup_cleanup.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/main.py app/repositories/runs.py tests/test_startup_cleanup.py
git commit -m "feat: interrupt stale in-process runs on startup"
```

### Task 16: Add README API Notes

**Files:**
- Modify: `README.md`

**Step 1: Document local setup**

Add:

````markdown
## Development

```bash
uv sync
uv run alembic upgrade head
uv run fastapi dev
```
````

**Step 2: Document v1 API surface**

Add endpoint list:

```text
GET  /api/sop/environments
GET  /api/sop/{sop_id}?env=dev
POST /api/sop/{sop_id}/runs?env=dev
GET  /api/sop/{sop_id}/runs?env=dev
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events?after=0
```

Mention that SOP fetching is mocked in v1.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document SOP run APIs"
```

### Task 17: Run Full Verification

**Files:**
- Verify all changed files

**Step 1: Run tests**

Run:

```bash
uv run pytest -v
```

Expected: PASS, except DB tests may require `TEST_DATABASE_URL` and local
Postgres 13.22.

**Step 2: Run migration check**

Run:

```bash
uv run alembic upgrade head
```

Expected: PASS against a local Postgres database.

**Step 3: Start local server**

Run:

```bash
uv run fastapi dev
```

Expected: server starts with app entrypoint `app.main:app`.

**Step 4: Smoke test API**

Run in another terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/sop/environments
curl "http://127.0.0.1:8000/api/sop/release-checklist?env=dev"
curl -X POST "http://127.0.0.1:8000/api/sop/release-checklist/runs?env=dev"
```

Expected: health returns `{"status":"ok"}`, environments return public envs,
SOP preview returns mock SOP data, and run creation returns `202 Accepted`.

**Step 5: Final commit if needed**

If verification required fixes:

```bash
git add .
git commit -m "fix: complete SOP run API verification"
```

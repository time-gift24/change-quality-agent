# MCP Runtime Manager Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the backend foundation for managing MCP server configuration, stdio lifecycle, health checks, and tool discovery.

**Architecture:** Add a separate MCP backend domain with SQLAlchemy models, repository methods, Pydantic schemas, FastAPI routes, and an in-process runtime manager. Postgres remains the durable source of truth, while `McpRuntimeManager` owns live stdio MCP sessions and reconciles user-visible runtime snapshots.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy async, Alembic, Postgres JSONB, pytest, httpx ASGI tests, official MCP Python SDK.

---

## References

- Design doc: `docs/plans/2026-05-26-mcp-runtime-manager-design.md`
- API style: `app/api/v1/runs.py`, `app/api/v1/sop.py`
- Repository style: `app/repositories/runs.py`
- Model style: `app/models/runs.py`
- Existing OpenAPI contract: `api/openapi.yml`
- Relevant skills: @fastapi, @project-structure, @superpowers:test-driven-development

The official MCP Python SDK v1.x exposes `ClientSession`,
`StdioServerParameters`, and `stdio_client`; use those APIs for the real stdio
transport implementation.

## Task 1: Add MCP SDK Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Step 1: Add the dependency**

Run:

```bash
uv add mcp
```

Expected: `pyproject.toml` gains an `mcp` dependency and `uv.lock` updates.

**Step 2: Verify imports**

Run:

```bash
uv run python -c "from mcp import ClientSession, StdioServerParameters; from mcp.client.stdio import stdio_client; print('ok')"
```

Expected: prints `ok`.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add mcp sdk dependency"
```

## Task 2: Add MCP Models and Migration

**Files:**
- Create: `app/models/mcp.py`
- Modify: `app/models/__init__.py`
- Create: `migrations/versions/20260526_0002_create_mcp_servers.py`
- Modify: `tests/test_models.py`

**Step 1: Write the failing model tests**

Add to `tests/test_models.py`:

```python
from app.models.mcp import McpServer, McpServerTool


def test_mcp_server_model_table_name() -> None:
    assert McpServer.__tablename__ == "mcp_servers"


def test_mcp_server_model_has_status_columns() -> None:
    columns = McpServer.__table__.columns

    assert "enabled" in columns
    assert "desired_state" in columns
    assert "runtime_status" in columns
    assert "last_checked_at" in columns
    assert "last_error" in columns


def test_mcp_server_tool_model_table_name() -> None:
    assert McpServerTool.__tablename__ == "mcp_server_tools"
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL because `app.models.mcp` does not exist.

**Step 3: Create the models**

Create `app/models/mcp.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class McpServer(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (
        Index("uq_mcp_servers_name", "name", unique=True),
        Index("ix_mcp_servers_enabled_desired_state", "enabled", "desired_state"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    command: Mapped[str | None] = mapped_column(Text)
    args: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    env: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    url: Mapped[str | None] = mapped_column(Text)
    headers: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    desired_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="stopped",
    )
    runtime_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    tools: Mapped[list["McpServerTool"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
    )


class McpServerTool(Base):
    __tablename__ = "mcp_server_tools"
    __table_args__ = (
        Index("uq_mcp_server_tools_server_name", "server_id", "name", unique=True),
        Index("ix_mcp_server_tools_server_id", "server_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    server: Mapped[McpServer] = relationship(back_populates="tools")
```

Update `app/models/__init__.py` if needed so the models are imported by metadata
creation paths.

**Step 4: Create the Alembic migration**

Create `migrations/versions/20260526_0002_create_mcp_servers.py` with tables,
indexes, and downgrade drops. Match existing migration style in
`migrations/versions/20260525_0001_create_runs.py`.

**Step 5: Run tests**

Run:

```bash
uv run pytest tests/test_models.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/models/mcp.py app/models/__init__.py migrations/versions/20260526_0002_create_mcp_servers.py tests/test_models.py
git commit -m "feat: add mcp database models"
```

## Task 3: Add MCP Schemas and Redaction

**Files:**
- Create: `app/schemas/mcp.py`
- Modify: `app/schemas/__init__.py`
- Create: `tests/test_mcp_schemas.py`

**Step 1: Write failing schema tests**

Create `tests/test_mcp_schemas.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.mcp import (
    McpServerDetail,
    McpServerRuntimeStatus,
    McpServerTool,
    McpTransport,
)


def test_mcp_server_response_redacts_env_and_headers() -> None:
    server = McpServerDetail(
        id=uuid4(),
        name="filesystem",
        transport=McpTransport.stdio,
        command="uvx",
        args=["mcp-server-filesystem"],
        env={"TOKEN": "secret"},
        url=None,
        headers={"Authorization": "Bearer secret"},
        enabled=True,
        desired_state="running",
        runtime_status=McpServerRuntimeStatus.running,
        last_checked_at=datetime.now(UTC),
        last_error=None,
        tool_count=0,
        tools=[],
    )

    body = server.model_dump(mode="json")

    assert body["env"] == {"TOKEN": "********"}
    assert body["headers"] == {"Authorization": "********"}


def test_mcp_tool_schema_defaults_input_schema() -> None:
    tool = McpServerTool(name="search", description=None)

    assert tool.input_schema == {}
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_mcp_schemas.py -v
```

Expected: FAIL because `app.schemas.mcp` does not exist.

**Step 3: Implement schemas**

Create `app/schemas/mcp.py`:

```python
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


REDACTED = "********"


class McpTransport(StrEnum):
    stdio = "stdio"
    http = "http"


class McpDesiredState(StrEnum):
    running = "running"
    stopped = "stopped"


class McpServerRuntimeStatus(StrEnum):
    unknown = "unknown"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    stopped = "stopped"
    error = "error"


class McpServerTool(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict = Field(default_factory=dict)
    discovered_at: datetime | None = None


class McpServerCreate(BaseModel):
    name: str
    transport: McpTransport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False
    desired_state: McpDesiredState = McpDesiredState.stopped

    @model_validator(mode="after")
    def validate_transport_fields(self):
        if self.transport == McpTransport.stdio and not self.command:
            raise ValueError("stdio MCP servers require command")
        if self.transport == McpTransport.http and not self.url:
            raise ValueError("http MCP servers require url")
        return self


class McpServerUpdate(BaseModel):
    name: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    enabled: bool | None = None
    desired_state: McpDesiredState | None = None


class McpServerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    transport: McpTransport
    command: str | None
    args: list[str]
    env: dict[str, str]
    url: str | None
    headers: dict[str, str]
    enabled: bool
    desired_state: McpDesiredState
    runtime_status: McpServerRuntimeStatus
    last_checked_at: datetime | None
    last_error: str | None
    tool_count: int = 0

    @field_serializer("env", "headers")
    def redact_mapping(self, value: dict[str, str]) -> dict[str, str]:
        return {key: REDACTED for key in value}


class McpServerDetail(McpServerSummary):
    tools: list[McpServerTool] = Field(default_factory=list)


class McpLifecycleResponse(BaseModel):
    server_id: UUID
    desired_state: McpDesiredState
    runtime_status: McpServerRuntimeStatus
    last_checked_at: datetime | None
    last_error: str | None
    tool_count: int
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_mcp_schemas.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/schemas/mcp.py app/schemas/__init__.py tests/test_mcp_schemas.py
git commit -m "feat: add mcp schemas"
```

## Task 4: Add MCP Repository

**Files:**
- Create: `app/repositories/mcp_servers.py`
- Modify: `app/repositories/__init__.py`
- Create: `tests/test_mcp_repository.py`

**Step 1: Write failing repository tests**

Create `tests/test_mcp_repository.py` using the same database fixture style as
`tests/test_run_repository.py`:

```python
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.mcp_servers import McpServerRepository
from app.schemas.mcp import McpDesiredState, McpServerRuntimeStatus, McpTransport

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


async def test_create_and_get_mcp_server(session) -> None:
    repository = McpServerRepository(session)

    server = await repository.create_server(
        name="filesystem",
        transport=McpTransport.stdio.value,
        command="uvx",
        args=["mcp-server-filesystem"],
        env={"TOKEN": "secret"},
        url=None,
        headers={},
        enabled=True,
        desired_state=McpDesiredState.running.value,
    )

    fetched = await repository.get_server(server.id)

    assert fetched is not None
    assert fetched.name == "filesystem"
    assert fetched.command == "uvx"


async def test_replace_tools_replaces_existing_snapshot(session) -> None:
    repository = McpServerRepository(session)
    server = await repository.create_server(
        name="filesystem",
        transport="stdio",
        command="uvx",
        args=[],
        env={},
        url=None,
        headers={},
        enabled=False,
        desired_state="stopped",
    )

    await repository.replace_tools(
        server.id,
        [{"name": "old", "description": None, "input_schema": {}}],
    )
    await repository.replace_tools(
        server.id,
        [{"name": "new", "description": "New tool", "input_schema": {"type": "object"}}],
    )

    fetched = await repository.get_server(server.id)

    assert [tool.name for tool in fetched.tools] == ["new"]
    assert fetched.tools[0].input_schema == {"type": "object"}


async def test_update_runtime_status(session) -> None:
    repository = McpServerRepository(session)
    server = await repository.create_server(
        name="filesystem",
        transport="stdio",
        command="uvx",
        args=[],
        env={},
        url=None,
        headers={},
        enabled=False,
        desired_state="stopped",
    )

    updated = await repository.update_runtime_status(
        server.id,
        runtime_status=McpServerRuntimeStatus.error.value,
        last_error="boom",
    )

    assert updated.runtime_status == "error"
    assert updated.last_error == "boom"
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_mcp_repository.py -v
```

Expected: skipped without `TEST_DATABASE_URL`, or FAIL if database tests are
enabled because repository does not exist.

**Step 3: Implement repository**

Create `app/repositories/mcp_servers.py` with:

```python
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mcp import McpServer, McpServerTool


class McpServerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_server(self, **values: Any) -> McpServer:
        server = McpServer(**values)
        self._session.add(server)
        await self._session.flush()
        return server

    async def list_servers(self) -> list[McpServer]:
        statement = (
            select(McpServer)
            .options(selectinload(McpServer.tools))
            .order_by(McpServer.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_startup_servers(self) -> list[McpServer]:
        statement = (
            select(McpServer)
            .where(McpServer.enabled.is_(True))
            .where(McpServer.desired_state == "running")
            .order_by(McpServer.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_server(self, server_id: UUID) -> McpServer | None:
        statement = (
            select(McpServer)
            .options(selectinload(McpServer.tools))
            .where(McpServer.id == server_id)
        )
        return await self._session.scalar(statement)

    async def require_server(self, server_id: UUID) -> McpServer:
        server = await self.get_server(server_id)
        if server is None:
            raise KeyError(server_id)
        return server

    async def update_server(self, server_id: UUID, **values: Any) -> McpServer:
        server = await self.require_server(server_id)
        for key, value in values.items():
            if value is not None:
                setattr(server, key, value)
        await self._session.flush()
        return server

    async def delete_server(self, server_id: UUID) -> None:
        server = await self.require_server(server_id)
        await self._session.delete(server)
        await self._session.flush()

    async def update_desired_state(
        self,
        server_id: UUID,
        desired_state: str,
    ) -> McpServer:
        return await self.update_server(server_id, desired_state=desired_state)

    async def update_runtime_status(
        self,
        server_id: UUID,
        *,
        runtime_status: str,
        last_error: str | None = None,
        checked: bool = False,
    ) -> McpServer:
        server = await self.require_server(server_id)
        server.runtime_status = runtime_status
        server.last_error = last_error
        if checked:
            server.last_checked_at = datetime.now(UTC)
        await self._session.flush()
        return server

    async def replace_tools(
        self,
        server_id: UUID,
        tools: list[dict[str, Any]],
    ) -> list[McpServerTool]:
        await self._session.execute(
            delete(McpServerTool).where(McpServerTool.server_id == server_id)
        )
        discovered_at = datetime.now(UTC)
        tool_models = [
            McpServerTool(
                server_id=server_id,
                name=tool["name"],
                description=tool.get("description"),
                input_schema=tool.get("input_schema") or {},
                discovered_at=discovered_at,
            )
            for tool in tools
        ]
        self._session.add_all(tool_models)
        await self._session.flush()
        return tool_models

    async def tool_count(self, server_id: UUID) -> int:
        statement = select(func.count()).select_from(McpServerTool).where(
            McpServerTool.server_id == server_id
        )
        return int((await self._session.scalar(statement)) or 0)

    async def commit(self) -> None:
        await self._session.commit()
```

Adjust signatures during implementation if schema objects are easier to pass,
but keep repository independent of HTTP request models where possible.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_models.py tests/test_mcp_repository.py -v
```

Expected: model tests PASS; repository tests either PASS with
`TEST_DATABASE_URL` or SKIP without it.

**Step 5: Commit**

```bash
git add app/repositories/mcp_servers.py app/repositories/__init__.py tests/test_mcp_repository.py
git commit -m "feat: add mcp server repository"
```

## Task 5: Add Runtime Manager with Fake Transport Tests

**Files:**
- Create: `app/services/mcp_runtime.py`
- Create: `tests/test_mcp_runtime.py`

**Step 1: Write failing runtime tests**

Create `tests/test_mcp_runtime.py`:

```python
from uuid import uuid4

import pytest

from app.schemas.mcp import McpServerRuntimeStatus
from app.services.mcp_runtime import McpRuntimeManager, UnsupportedMcpTransportError


class FakeServer:
    def __init__(self, *, transport: str = "stdio") -> None:
        self.id = uuid4()
        self.name = "filesystem"
        self.transport = transport
        self.command = "uvx"
        self.args = []
        self.env = {}
        self.url = None
        self.headers = {}
        self.desired_state = "stopped"
        self.runtime_status = "unknown"
        self.last_checked_at = None
        self.last_error = None
        self.tools = []


class FakeRepository:
    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.tools = []

    async def require_server(self, server_id):
        assert server_id == self.server.id
        return self.server

    async def update_desired_state(self, server_id, desired_state):
        self.server.desired_state = desired_state
        return self.server

    async def update_runtime_status(self, server_id, *, runtime_status, last_error=None, checked=False):
        self.server.runtime_status = runtime_status
        self.server.last_error = last_error
        return self.server

    async def replace_tools(self, server_id, tools):
        self.tools = tools
        return []

    async def tool_count(self, server_id):
        return len(self.tools)

    async def commit(self):
        return None


class FakeProbe:
    async def start(self, server):
        return object(), [{"name": "search", "description": "Search", "input_schema": {}}]

    async def stop(self, handle):
        return None


@pytest.mark.asyncio
async def test_start_sets_running_and_stores_tools() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=FakeProbe())

    status = await manager.start(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.running
    assert server.desired_state == "running"
    assert repository.tools[0]["name"] == "search"


@pytest.mark.asyncio
async def test_stop_is_idempotent_without_handle() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=FakeProbe())

    status = await manager.stop(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.stopped
    assert server.desired_state == "stopped"


@pytest.mark.asyncio
async def test_http_start_is_unsupported_in_v1() -> None:
    server = FakeServer(transport="http")
    repository = FakeRepository(server)
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=FakeProbe())

    with pytest.raises(UnsupportedMcpTransportError):
        await manager.start(server.id)
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_mcp_runtime.py -v
```

Expected: FAIL because `app.services.mcp_runtime` does not exist.

**Step 3: Implement runtime manager interfaces**

Create `app/services/mcp_runtime.py` with:

```python
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.schemas.mcp import (
    McpDesiredState,
    McpLifecycleResponse,
    McpServerRuntimeStatus,
)


class UnsupportedMcpTransportError(Exception):
    pass


class McpCommandNotAllowedError(Exception):
    pass


@dataclass
class McpRuntimeHandle:
    exit_stack: AsyncExitStack
    session: ClientSession


class StdioMcpProbe:
    def __init__(self, allowed_commands: set[str] | None = None) -> None:
        self._allowed_commands = allowed_commands or {"uvx", "npx", "node", "python"}

    async def start(self, server) -> tuple[McpRuntimeHandle, list[dict[str, Any]]]:
        if server.command not in self._allowed_commands:
            raise McpCommandNotAllowedError(server.command or "")

        exit_stack = AsyncExitStack()
        try:
            params = StdioServerParameters(
                command=server.command,
                args=server.args,
                env=server.env,
            )
            read, write = await exit_stack.enter_async_context(stdio_client(params))
            session = await exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools_result = await session.list_tools()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema or {},
                }
                for tool in tools_result.tools
            ]
            return McpRuntimeHandle(exit_stack=exit_stack, session=session), tools
        except Exception:
            await exit_stack.aclose()
            raise

    async def stop(self, handle: McpRuntimeHandle) -> None:
        await handle.exit_stack.aclose()


class McpRuntimeManager:
    def __init__(
        self,
        *,
        repository_factory: Callable[[], Any],
        probe: StdioMcpProbe | None = None,
    ) -> None:
        self._repository_factory = repository_factory
        self._probe = probe or StdioMcpProbe()
        self._handles: dict[UUID, McpRuntimeHandle] = {}

    async def start(self, server_id: UUID) -> McpLifecycleResponse:
        repository = self._repository_factory()
        await repository.update_desired_state(server_id, McpDesiredState.running.value)
        server = await repository.require_server(server_id)
        if server.transport != "stdio":
            raise UnsupportedMcpTransportError(server.transport)
        if server_id in self._handles:
            return await self._response(repository, server_id)

        await repository.update_runtime_status(
            server_id,
            runtime_status=McpServerRuntimeStatus.starting.value,
        )
        try:
            handle, tools = await self._probe.start(server)
        except Exception as exc:
            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.error.value,
                last_error=str(exc),
                checked=True,
            )
            await repository.commit()
            raise

        self._handles[server_id] = handle
        await repository.replace_tools(server_id, tools)
        await repository.update_runtime_status(
            server_id,
            runtime_status=McpServerRuntimeStatus.running.value,
            last_error=None,
            checked=True,
        )
        await repository.commit()
        return await self._response(repository, server_id)

    async def stop(self, server_id: UUID) -> McpLifecycleResponse:
        repository = self._repository_factory()
        await repository.update_desired_state(server_id, McpDesiredState.stopped.value)
        await repository.update_runtime_status(
            server_id,
            runtime_status=McpServerRuntimeStatus.stopping.value,
        )
        handle = self._handles.pop(server_id, None)
        if handle is not None:
            await self._probe.stop(handle)
        await repository.update_runtime_status(
            server_id,
            runtime_status=McpServerRuntimeStatus.stopped.value,
            last_error=None,
        )
        await repository.commit()
        return await self._response(repository, server_id)

    async def restart(self, server_id: UUID) -> McpLifecycleResponse:
        await self.stop(server_id)
        return await self.start(server_id)

    async def check(self, server_id: UUID) -> McpLifecycleResponse:
        repository = self._repository_factory()
        server = await repository.require_server(server_id)
        if server.transport != "stdio":
            raise UnsupportedMcpTransportError(server.transport)

        if server_id in self._handles:
            handle, tools = self._handles[server_id], None
            tools_result = await handle.session.list_tools()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema or {},
                }
                for tool in tools_result.tools
            ]
        else:
            handle, tools = await self._probe.start(server)
            await self._probe.stop(handle)

        await repository.replace_tools(server_id, tools)
        await repository.update_runtime_status(
            server_id,
            runtime_status=server.runtime_status,
            last_error=None,
            checked=True,
        )
        await repository.commit()
        return await self._response(repository, server_id)

    async def shutdown(self) -> None:
        for server_id in list(self._handles):
            await self.stop(server_id)

    async def _response(self, repository, server_id: UUID) -> McpLifecycleResponse:
        server = await repository.require_server(server_id)
        return McpLifecycleResponse(
            server_id=server.id,
            desired_state=server.desired_state,
            runtime_status=server.runtime_status,
            last_checked_at=server.last_checked_at,
            last_error=server.last_error,
            tool_count=await repository.tool_count(server_id),
        )
```

This is the starting shape. During implementation, tighten exception handling so
unsupported transport returns HTTP errors at the API boundary, while unexpected
runtime failures update database state before propagating.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_mcp_runtime.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/services/mcp_runtime.py tests/test_mcp_runtime.py
git commit -m "feat: add mcp runtime manager"
```

## Task 6: Add FastAPI Dependencies

**Files:**
- Modify: `app/api/deps.py`
- Create: `tests/test_mcp_api_dependencies.py`

**Step 1: Write failing dependency tests**

Create `tests/test_mcp_api_dependencies.py`:

```python
from app.api.deps import get_mcp_repository, get_mcp_runtime_manager
from app.repositories.mcp_servers import McpServerRepository
from app.services.mcp_runtime import McpRuntimeManager


def test_mcp_runtime_manager_singleton() -> None:
    first = get_mcp_runtime_manager()
    second = get_mcp_runtime_manager()

    assert isinstance(first, McpRuntimeManager)
    assert first is second
```

Do not call `get_mcp_repository` directly unless you provide a session; it is
covered through API tests.

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_mcp_api_dependencies.py -v
```

Expected: FAIL because dependencies do not exist.

**Step 3: Implement dependencies**

Modify `app/api/deps.py`:

```python
from app.repositories.mcp_servers import McpServerRepository
from app.services.mcp_runtime import McpRuntimeManager


def get_mcp_repository(session: SessionDep) -> McpServerRepository:
    return McpServerRepository(session)


McpRepositoryDep = Annotated[McpServerRepository, Depends(get_mcp_repository)]


_mcp_runtime_manager: McpRuntimeManager | None = None


def get_mcp_runtime_manager() -> McpRuntimeManager:
    global _mcp_runtime_manager
    if _mcp_runtime_manager is None:
        _mcp_runtime_manager = McpRuntimeManager(repository_factory=...)
    return _mcp_runtime_manager


McpRuntimeManagerDep = Annotated[McpRuntimeManager, Depends(get_mcp_runtime_manager)]
```

The repository factory needs an async session source. Prefer a small factory
function in `mcp_runtime.py` or `deps.py` that creates an `async_session()` and
returns a repository wrapped with commit behavior. Keep it testable by allowing
dependency overrides.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_mcp_api_dependencies.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/deps.py tests/test_mcp_api_dependencies.py
git commit -m "feat: wire mcp dependencies"
```

## Task 7: Add MCP API Routes

**Files:**
- Create: `app/api/v1/mcp.py`
- Modify: `app/api/v1/__init__.py`
- Modify: `app/main.py`
- Create: `tests/test_mcp_api.py`

**Step 1: Write failing API tests**

Create `tests/test_mcp_api.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_mcp_repository, get_mcp_runtime_manager
from app.main import app


class FakeTool:
    name = "search"
    description = "Search"
    input_schema = {}
    discovered_at = datetime.now(UTC)


class FakeServer:
    def __init__(self) -> None:
        self.id = uuid4()
        self.name = "filesystem"
        self.transport = "stdio"
        self.command = "uvx"
        self.args = ["mcp-server-filesystem"]
        self.env = {"TOKEN": "secret"}
        self.url = None
        self.headers = {}
        self.enabled = True
        self.desired_state = "running"
        self.runtime_status = "running"
        self.last_checked_at = datetime.now(UTC)
        self.last_error = None
        self.tools = [FakeTool()]


class FakeRepository:
    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.deleted = False

    async def list_servers(self):
        return [self.server]

    async def get_server(self, server_id):
        return self.server if server_id == self.server.id else None

    async def create_server(self, **values):
        for key, value in values.items():
            setattr(self.server, key, value)
        return self.server

    async def update_server(self, server_id, **values):
        for key, value in values.items():
            if value is not None:
                setattr(self.server, key, value)
        return self.server

    async def delete_server(self, server_id):
        self.deleted = True

    async def commit(self):
        return None


class FakeRuntimeManager:
    async def start(self, server_id):
        return {
            "server_id": server_id,
            "desired_state": "running",
            "runtime_status": "running",
            "last_checked_at": datetime.now(UTC),
            "last_error": None,
            "tool_count": 1,
        }

    stop = start
    restart = start
    check = start


@pytest.fixture(autouse=True)
def overrides():
    server = FakeServer()
    repository = FakeRepository(server)
    app.dependency_overrides[get_mcp_repository] = lambda: repository
    app.dependency_overrides[get_mcp_runtime_manager] = lambda: FakeRuntimeManager()
    yield server, repository
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_mcp_servers_redacts_env(overrides) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/mcp/servers")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["env"] == {"TOKEN": "********"}
    assert body[0]["tool_count"] == 1


@pytest.mark.asyncio
async def test_start_mcp_server_returns_runtime_status(overrides) -> None:
    server, _ = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(f"/api/mcp/servers/{server.id}/start")

    assert response.status_code == 200
    assert response.json()["runtime_status"] == "running"
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_mcp_api.py -v
```

Expected: FAIL with 404 because routes do not exist.

**Step 3: Implement routes**

Create `app/api/v1/mcp.py`:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, status

from app.api.deps import McpRepositoryDep, McpRuntimeManagerDep
from app.schemas.mcp import (
    McpLifecycleResponse,
    McpServerCreate,
    McpServerDetail,
    McpServerSummary,
    McpServerTool,
    McpServerUpdate,
)
from app.services.mcp_runtime import UnsupportedMcpTransportError

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


def _tool_count(server) -> int:
    return len(getattr(server, "tools", []) or [])


def _summary(server) -> McpServerSummary:
    return McpServerSummary.model_validate(server, from_attributes=True).model_copy(
        update={"tool_count": _tool_count(server)}
    )


def _detail(server) -> McpServerDetail:
    summary = _summary(server).model_dump()
    tools = [
        McpServerTool(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            discovered_at=tool.discovered_at,
        )
        for tool in getattr(server, "tools", []) or []
    ]
    return McpServerDetail(**summary, tools=tools)


@router.get("/servers", response_model=list[McpServerSummary])
async def list_mcp_servers(repository: McpRepositoryDep) -> list[McpServerSummary]:
    servers = await repository.list_servers()
    return [_summary(server) for server in servers]


@router.post(
    "/servers",
    response_model=McpServerDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_server(
    payload: McpServerCreate,
    repository: McpRepositoryDep,
) -> McpServerDetail:
    server = await repository.create_server(**payload.model_dump(mode="json"))
    await repository.commit()
    return _detail(server)


@router.get("/servers/{server_id}", response_model=McpServerDetail)
async def get_mcp_server(
    server_id: Annotated[UUID, Path()],
    repository: McpRepositoryDep,
) -> McpServerDetail:
    server = await repository.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found.")
    return _detail(server)


@router.patch("/servers/{server_id}", response_model=McpServerDetail)
async def update_mcp_server(
    server_id: Annotated[UUID, Path()],
    payload: McpServerUpdate,
    repository: McpRepositoryDep,
) -> McpServerDetail:
    server = await repository.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found.")
    if server.runtime_status == "running":
        raise HTTPException(
            status_code=409,
            detail="Stop the MCP server before updating its configuration.",
        )
    values = payload.model_dump(exclude_unset=True, mode="json")
    server = await repository.update_server(server_id, **values)
    await repository.commit()
    return _detail(server)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    server_id: Annotated[UUID, Path()],
    repository: McpRepositoryDep,
    runtime: McpRuntimeManagerDep,
) -> None:
    server = await repository.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found.")
    if server.runtime_status == "running":
        await runtime.stop(server_id)
    await repository.delete_server(server_id)
    await repository.commit()


async def _run_lifecycle(operation, server_id: UUID) -> McpLifecycleResponse:
    try:
        result = await operation(server_id)
    except UnsupportedMcpTransportError as exc:
        raise HTTPException(status_code=422, detail=f"Unsupported MCP transport: {exc}") from exc
    if isinstance(result, dict):
        return McpLifecycleResponse(**result)
    return result


@router.post("/servers/{server_id}/start", response_model=McpLifecycleResponse)
async def start_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.start, server_id)


@router.post("/servers/{server_id}/stop", response_model=McpLifecycleResponse)
async def stop_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.stop, server_id)


@router.post("/servers/{server_id}/restart", response_model=McpLifecycleResponse)
async def restart_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.restart, server_id)


@router.post("/servers/{server_id}/check", response_model=McpLifecycleResponse)
async def check_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.check, server_id)
```

Register the router in `app/main.py`:

```python
from app.api.v1 import mcp, runs, sop

app.include_router(mcp.router)
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_mcp_api.py tests/test_mcp_schemas.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/v1/mcp.py app/api/v1/__init__.py app/main.py tests/test_mcp_api.py
git commit -m "feat: add mcp management api"
```

## Task 8: Wire Lifespan Startup and Shutdown

**Files:**
- Modify: `app/main.py`
- Modify: `app/services/mcp_runtime.py`
- Create: `tests/test_mcp_lifespan.py`

**Step 1: Write failing lifespan tests**

Create `tests/test_mcp_lifespan.py`:

```python
import pytest

from app.services.mcp_runtime import McpRuntimeManager


class FakeRepository:
    async def list_startup_servers(self):
        return []

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_runtime_startup_loads_startup_servers() -> None:
    called = False

    class Runtime(McpRuntimeManager):
        async def start_enabled_servers(self):
            nonlocal called
            called = True

    manager = Runtime(repository_factory=lambda: FakeRepository())

    await manager.start_enabled_servers()

    assert called
```

Prefer direct runtime tests over fragile whole-app lifespan tests. If the app
lifespan is tested, use dependency injection and fake managers.

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_mcp_lifespan.py -v
```

Expected: FAIL until startup method exists or test is adjusted to concrete
behavior.

**Step 3: Implement startup behavior**

Add to `McpRuntimeManager`:

```python
async def start_enabled_servers(self) -> None:
    repository = self._repository_factory()
    servers = await repository.list_startup_servers()
    for server in servers:
        try:
            await self.start(server.id)
        except Exception:
            continue
```

Update `app/main.py` lifespan:

```python
from app.api.deps import get_mcp_runtime_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await interrupt_leftover_runs()
    mcp_runtime = get_mcp_runtime_manager()
    await mcp_runtime.start_enabled_servers()
    try:
        yield
    finally:
        await mcp_runtime.shutdown()
```

Keep startup best-effort: one MCP server failure should not prevent the whole
API from starting, because failures are reflected in MCP runtime status.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_mcp_runtime.py tests/test_startup_cleanup.py tests/test_mcp_lifespan.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/main.py app/services/mcp_runtime.py tests/test_mcp_lifespan.py
git commit -m "feat: start mcp servers during lifespan"
```

## Task 9: Add OpenAPI Contract

**Files:**
- Modify: `api/openapi.yml`
- Create or modify: `tests/test_openapi_contract.py`

**Step 1: Write failing contract test**

If no OpenAPI contract test exists, create `tests/test_openapi_contract.py`:

```python
from pathlib import Path

import yaml


def test_openapi_includes_mcp_server_routes() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text())
    paths = spec["paths"]

    assert "/api/mcp/servers" in paths
    assert "/api/mcp/servers/{server_id}/start" in paths
    assert "/api/mcp/servers/{server_id}/check" in paths
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -v
```

Expected: FAIL because MCP paths are not in the contract.

**Step 3: Update OpenAPI**

Update `api/openapi.yml`:

- Add tag `mcp`.
- Add paths for collection, detail, and lifecycle operations.
- Add schemas for:
  - `McpTransport`
  - `McpDesiredState`
  - `McpRuntimeStatus`
  - `McpServerCreate`
  - `McpServerUpdate`
  - `McpServerSummary`
  - `McpServerDetail`
  - `McpServerTool`
  - `McpLifecycleResponse`

Use examples that show redacted response env/header values:

```yaml
env:
  type: object
  additionalProperties:
    type: string
  example:
    TOKEN: "********"
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add api/openapi.yml tests/test_openapi_contract.py
git commit -m "docs: add mcp api contract"
```

## Task 10: Add a Stub MCP Server Integration Test

**Files:**
- Create: `tests/fixtures/mcp_stub_server.py`
- Modify: `tests/test_mcp_runtime.py`

**Step 1: Create a minimal MCP stub server fixture**

Use the MCP SDK server primitives. Keep the stub tiny: one tool, no external
dependencies, no network.

Create `tests/fixtures/mcp_stub_server.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stub")


@mcp.tool()
def echo(value: str) -> str:
    return value


if __name__ == "__main__":
    mcp.run()
```

**Step 2: Add a runtime integration test**

Add to `tests/test_mcp_runtime.py`:

```python
@pytest.mark.asyncio
async def test_stdio_probe_discovers_stub_tools() -> None:
    server = FakeServer()
    server.command = "python"
    server.args = ["tests/fixtures/mcp_stub_server.py"]
    repository = FakeRepository(server)
    manager = McpRuntimeManager(repository_factory=lambda: repository)

    status = await manager.start(server.id)
    await manager.stop(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.running
    assert any(tool["name"] == "echo" for tool in repository.tools)
```

**Step 3: Run the integration test**

Run:

```bash
uv run pytest tests/test_mcp_runtime.py::test_stdio_probe_discovers_stub_tools -v
```

Expected: PASS and no leaked child process.

**Step 4: Run runtime tests**

Run:

```bash
uv run pytest tests/test_mcp_runtime.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/fixtures/mcp_stub_server.py tests/test_mcp_runtime.py
git commit -m "test: verify stdio mcp tool discovery"
```

## Task 11: Full Verification

**Files:**
- No code edits unless verification exposes issues.

**Step 1: Run the default test suite**

Run:

```bash
uv run pytest
```

Expected: all non-db tests pass; db tests skip unless `TEST_DATABASE_URL` is set.

**Step 2: Run database integration tests when available**

If `TEST_DATABASE_URL` is configured, run:

```bash
uv run pytest -m db
```

Expected: all DB tests pass.

**Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected: clean working tree.

**Step 4: Final commit only if fixes were needed**

If verification required small fixes:

```bash
git add <changed-files>
git commit -m "test: stabilize mcp runtime manager"
```

## Execution Notes

- Keep changes out of the main checkout. Work only inside the dedicated
  worktree.
- Do not commit `.agents/`, `skills-lock.json`, `.venv`, or local env files.
- Keep each Python file under 1000 lines.
- Use `Annotated` for FastAPI parameters and dependencies.
- Prefer fake runtime dependencies for API tests.
- Keep HTTP transport lifecycle unsupported in v1, but preserve schema support.
- Do not wire MCP tools into SOP runs or ReAct agents in this implementation.

Plan complete and saved to `docs/plans/2026-05-26-mcp-runtime-manager-implementation.md`.

Two execution options:

1. **Subagent-Driven (this session)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Parallel Session (separate)** - Open a new session with executing-plans, batch execution with checkpoints.

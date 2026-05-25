import os

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.mcp import McpServerTool
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


async def test_list_startup_servers_returns_enabled_running_servers(session) -> None:
    repository = McpServerRepository(session)
    startup_server = await repository.create_server(
        name="enabled-running",
        transport="stdio",
        command="uvx",
        args=[],
        env={},
        url=None,
        headers={},
        enabled=True,
        desired_state=McpDesiredState.running.value,
    )
    await repository.create_server(
        name="enabled-stopped",
        transport="stdio",
        command="uvx",
        args=[],
        env={},
        url=None,
        headers={},
        enabled=True,
        desired_state=McpDesiredState.stopped.value,
    )

    servers = await repository.list_startup_servers()

    assert [server.id for server in servers] == [startup_server.id]


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
        [
            {
                "name": "new",
                "description": "New tool",
                "input_schema": {"type": "object"},
            }
        ],
    )

    fetched = await repository.get_server(server.id)

    assert fetched is not None
    assert [tool.name for tool in fetched.tools] == ["new"]
    assert fetched.tools[0].input_schema == {"type": "object"}
    assert await repository.tool_count(server.id) == 1


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
        checked=True,
    )

    assert updated.runtime_status == "error"
    assert updated.last_error == "boom"
    assert updated.last_checked_at is not None


async def test_delete_server_cascades_tools(session) -> None:
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
        [{"name": "search", "description": None, "input_schema": {}}],
    )

    await repository.delete_server(server.id)
    remaining_tools = (
        await session.scalars(
            select(McpServerTool).where(McpServerTool.server_id == server.id)
        )
    ).all()

    assert await repository.get_server(server.id) is None
    assert remaining_tools == []

from uuid import uuid4

import pytest

from app import main
from app.schemas.mcp import McpDesiredState, McpServerRuntimeStatus
from app.services.mcp_runtime import McpRuntimeManager


class FakeStartupServer:
    def __init__(self, name: str) -> None:
        self.id = uuid4()
        self.name = name
        self.transport = "stdio"
        self.command = "uvx"
        self.args = []
        self.env = {}
        self.url = None
        self.headers = {}
        self.enabled = True
        self.desired_state = McpDesiredState.running.value
        self.runtime_status = McpServerRuntimeStatus.unknown.value
        self.last_checked_at = None
        self.last_error = None
        self.tools = []


class FakeStartupRepository:
    def __init__(self) -> None:
        self.servers = [FakeStartupServer("server-1"), FakeStartupServer("server-2")]
        self.tools = []
        self.commits = 0

    async def list_startup_servers(self) -> object:
        return self.servers

    async def require_server(self, server_id: object) -> object:
        return next(server for server in self.servers if server.id == server_id)

    async def update_desired_state(
        self, server_id: object, desired_state: object
    ) -> object:
        server = await self.require_server(server_id)
        server.desired_state = desired_state
        return server

    async def update_runtime_status(
        self,
        server_id: object,
        *,
        runtime_status: object,
        last_error: object = None,
        checked: object = False,
    ) -> object:
        server = await self.require_server(server_id)
        server.runtime_status = runtime_status
        server.last_error = last_error
        return server

    async def replace_tools(self, server_id: object, tools: object) -> object:
        self.tools = tools
        return []

    async def tool_count(self, server_id: object) -> object:
        return len(self.tools)

    async def commit(self) -> None:
        self.commits += 1


class FakeProbe:
    def __init__(self) -> None:
        self.started = []

    async def start(self, server: object) -> object:
        self.started.append(server.id)
        return object(), []

    async def list_tools(self, handle: object) -> object:
        return []

    async def stop(self, handle: object) -> None:
        return None


@pytest.mark.asyncio
async def test_runtime_start_enabled_servers_starts_startup_servers() -> None:
    repository = FakeStartupRepository()
    probe = FakeProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start_enabled_servers()

    assert probe.started == [server.id for server in repository.servers]
    assert [server.runtime_status for server in repository.servers] == [
        McpServerRuntimeStatus.running.value,
        McpServerRuntimeStatus.running.value,
    ]


@pytest.mark.asyncio
async def test_runtime_start_enabled_servers_starts_http_servers() -> None:
    repository = FakeStartupRepository()
    repository.servers = [FakeStartupServer("http-server")]
    repository.servers[0].transport = "http"
    repository.servers[0].url = "https://example.com/mcp"
    probe = FakeProbe()
    manager = McpRuntimeManager(
        repository_factory=lambda: repository,
        probe=probe,
    )

    await manager.start_enabled_servers()

    assert probe.started == [repository.servers[0].id]
    assert repository.servers[0].runtime_status == McpServerRuntimeStatus.running.value
    assert repository.servers[0].last_error is None
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_runtime_start_skips_without_single_instance_confirmation() -> None:
    repository = FakeStartupRepository()
    probe = FakeProbe()
    manager = McpRuntimeManager(
        repository_factory=lambda: repository,
        probe=probe,
        single_instance_confirmed=False,
    )

    await manager.start_enabled_servers()

    assert probe.started == []
    assert [server.runtime_status for server in repository.servers] == [
        McpServerRuntimeStatus.error.value,
        McpServerRuntimeStatus.error.value,
    ]
    assert repository.commits == 2


@pytest.mark.asyncio
async def test_lifespan_starts_and_shuts_down_mcp_runtime(monkeypatch: object) -> None:
    events = []

    async def fake_interrupt_leftover_sop_quality_checks() -> None:
        events.append("interrupt")

    class FakeRuntime:
        async def start_enabled_servers(self) -> None:
            events.append("mcp-start")

        async def shutdown(self) -> None:
            events.append("mcp-shutdown")

    monkeypatch.setattr(
        main,
        "interrupt_leftover_sop_quality_checks",
        fake_interrupt_leftover_sop_quality_checks,
    )
    monkeypatch.setattr(main, "get_mcp_runtime_manager", lambda: FakeRuntime())

    async with main.lifespan(main.app):
        assert events == ["interrupt", "mcp-start"]

    assert events == ["interrupt", "mcp-start", "mcp-shutdown"]

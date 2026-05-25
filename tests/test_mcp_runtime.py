from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.mcp import McpDesiredState, McpServerRuntimeStatus
from app.services.mcp_runtime import McpRuntimeManager, UnsupportedMcpTransportError


class FakeServer:
    def __init__(self, *, transport: str = "stdio") -> None:
        self.id = uuid4()
        self.name = "filesystem"
        self.transport = transport
        self.command = "uvx"
        self.args = []
        self.env = {}
        self.url = "https://example.com/mcp" if transport == "http" else None
        self.headers = {}
        self.enabled = False
        self.desired_state = McpDesiredState.stopped.value
        self.runtime_status = McpServerRuntimeStatus.unknown.value
        self.last_checked_at = None
        self.last_error = None
        self.tools = []


class FakeRepository:
    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.tools = []
        self.commits = 0

    async def require_server(self, server_id):
        assert server_id == self.server.id
        return self.server

    async def update_desired_state(self, server_id, desired_state):
        assert server_id == self.server.id
        self.server.desired_state = desired_state
        return self.server

    async def update_runtime_status(
        self,
        server_id,
        *,
        runtime_status,
        last_error=None,
        checked=False,
    ):
        assert server_id == self.server.id
        self.server.runtime_status = runtime_status
        self.server.last_error = last_error
        if checked:
            self.server.last_checked_at = datetime.now(UTC)
        return self.server

    async def replace_tools(self, server_id, tools):
        assert server_id == self.server.id
        self.tools = tools
        self.server.tools = tools
        return []

    async def tool_count(self, server_id):
        assert server_id == self.server.id
        return len(self.tools)

    async def commit(self):
        self.commits += 1


class FakeProbe:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.listed = 0

    async def start(self, server):
        self.started += 1
        return (
            object(),
            [{"name": "search", "description": "Search", "input_schema": {}}],
        )

    async def list_tools(self, handle):
        self.listed += 1
        return [
            {"name": "search", "description": "Search", "input_schema": {}}
        ]

    async def stop(self, handle):
        self.stopped += 1


class FailingProbe(FakeProbe):
    async def start(self, server):
        raise RuntimeError("boom")


class FailingListProbe(FakeProbe):
    async def list_tools(self, handle):
        raise RuntimeError("list failed")


@pytest.mark.asyncio
async def test_start_sets_running_and_stores_tools() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FakeProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    status = await manager.start(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.running
    assert status.desired_state == McpDesiredState.running
    assert server.desired_state == McpDesiredState.running.value
    assert repository.tools[0]["name"] == "search"
    assert probe.started == 1
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_stop_is_idempotent_without_handle() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=FakeProbe())

    status = await manager.stop(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.stopped
    assert status.desired_state == McpDesiredState.stopped
    assert server.desired_state == McpDesiredState.stopped.value


@pytest.mark.asyncio
async def test_http_start_is_unsupported_in_v1() -> None:
    server = FakeServer(transport="http")
    repository = FakeRepository(server)
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=FakeProbe())

    with pytest.raises(UnsupportedMcpTransportError):
        await manager.start(server.id)

    assert server.desired_state == McpDesiredState.stopped.value


@pytest.mark.asyncio
async def test_start_failure_records_error_status() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    manager = McpRuntimeManager(
        repository_factory=lambda: repository,
        probe=FailingProbe(),
    )

    with pytest.raises(RuntimeError):
        await manager.start(server.id)

    assert server.desired_state == McpDesiredState.running.value
    assert server.runtime_status == McpServerRuntimeStatus.error.value
    assert server.last_error == "boom"
    assert server.last_checked_at is not None
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_restart_stops_then_starts() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FakeProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start(server.id)
    status = await manager.restart(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.running
    assert status.desired_state == McpDesiredState.running
    assert probe.started == 2
    assert probe.stopped == 1


@pytest.mark.asyncio
async def test_check_temporary_session_does_not_change_desired_state() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FakeProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    status = await manager.check(server.id)

    assert status.desired_state == McpDesiredState.stopped
    assert status.runtime_status == McpServerRuntimeStatus.unknown
    assert repository.tools[0]["name"] == "search"
    assert probe.started == 1
    assert probe.stopped == 1


@pytest.mark.asyncio
async def test_check_failure_records_error_without_changing_desired_state() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    manager = McpRuntimeManager(
        repository_factory=lambda: repository,
        probe=FailingProbe(),
    )

    with pytest.raises(RuntimeError):
        await manager.check(server.id)

    assert server.desired_state == McpDesiredState.stopped.value
    assert server.runtime_status == McpServerRuntimeStatus.error.value
    assert server.last_error == "boom"
    assert server.last_checked_at is not None


@pytest.mark.asyncio
async def test_live_check_failure_records_error_without_stopping_handle() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FailingListProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start(server.id)
    with pytest.raises(RuntimeError):
        await manager.check(server.id)

    assert server.desired_state == McpDesiredState.running.value
    assert server.runtime_status == McpServerRuntimeStatus.error.value
    assert server.last_error == "list failed"
    assert probe.stopped == 0


@pytest.mark.asyncio
async def test_shutdown_stops_handles_without_changing_desired_state() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FakeProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start(server.id)
    await manager.shutdown()

    assert server.desired_state == McpDesiredState.running.value
    assert server.runtime_status == McpServerRuntimeStatus.stopped.value
    assert probe.stopped == 1

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.mcp import McpDesiredState, McpServerRuntimeStatus
import app.services.mcp_runtime as mcp_runtime_module
from app.services.mcp_runtime import (
    McpCommandNotAllowedError,
    McpRuntimeNotEnabledError,
    McpRuntimeManager,
    StdioMcpProbe,
    UnsupportedMcpTransportError,
)


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


class FakeRepositoryContext:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.repository

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True


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


class FlakyListProbe(FakeProbe):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_list = True

    async def list_tools(self, handle):
        if self.fail_next_list:
            self.fail_next_list = False
            raise RuntimeError("list failed")
        return await super().list_tools(handle)


class FailingStopProbe(FakeProbe):
    async def stop(self, handle):
        self.stopped += 1
        raise RuntimeError("stop failed")


class SlowProbe(FakeProbe):
    async def start(self, server):
        self.started += 1
        await asyncio.sleep(0.01)
        return object(), []


class HangingProbe(FakeProbe):
    async def start(self, server):
        await asyncio.sleep(1)
        return object(), []


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
async def test_start_requires_single_instance_confirmation() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FakeProbe()
    manager = McpRuntimeManager(
        repository_factory=lambda: repository,
        probe=probe,
        single_instance_confirmed=False,
    )

    with pytest.raises(McpRuntimeNotEnabledError):
        await manager.start(server.id)

    assert probe.started == 0
    assert server.runtime_status == McpServerRuntimeStatus.unknown.value


@pytest.mark.asyncio
async def test_concurrent_start_only_starts_one_handle() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = SlowProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    statuses = await asyncio.gather(manager.start(server.id), manager.start(server.id))

    assert [status.runtime_status for status in statuses] == [
        McpServerRuntimeStatus.running,
        McpServerRuntimeStatus.running,
    ]
    assert probe.started == 1


@pytest.mark.asyncio
async def test_start_timeout_records_error_status() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    manager = McpRuntimeManager(
        repository_factory=lambda: repository,
        probe=HangingProbe(),
        operation_timeout_seconds=0.01,
    )

    with pytest.raises(TimeoutError):
        await manager.start(server.id)

    assert server.runtime_status == McpServerRuntimeStatus.error.value
    assert server.last_error == "MCP operation timed out."
    assert server.last_checked_at is not None


@pytest.mark.asyncio
async def test_start_supports_repository_context_factory() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    repository_context = FakeRepositoryContext(repository)
    manager = McpRuntimeManager(
        repository_factory=lambda: repository_context,
        probe=FakeProbe(),
    )

    await manager.start(server.id)

    assert repository_context.entered is True
    assert repository_context.exited is True


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
async def test_stop_failure_keeps_handle_for_retry() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FailingStopProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start(server.id)
    with pytest.raises(RuntimeError):
        await manager.stop(server.id)

    assert manager.is_running(server.id) is True
    assert server.runtime_status == McpServerRuntimeStatus.error.value
    assert server.last_error == "stop failed"


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
async def test_stdio_probe_rejects_unregistered_command_args() -> None:
    server = FakeServer()
    server.command = "uvx"
    server.args = ["mcp-server-filesystem"]
    probe = StdioMcpProbe(
        allowed_commands={"uvx"},
        allowed_stdio_specs={"uvx:mcp-server-github"},
    )

    with pytest.raises(McpCommandNotAllowedError):
        await probe.start(server)


@pytest.mark.asyncio
async def test_stdio_probe_requires_spec_allowlist() -> None:
    server = FakeServer()
    server.command = "uvx"
    server.args = ["mcp-server-filesystem"]
    probe = StdioMcpProbe(allowed_commands={"uvx"})

    with pytest.raises(McpCommandNotAllowedError):
        await probe.start(server)


@pytest.mark.asyncio
async def test_stdio_probe_cleans_exit_stack_on_cancellation(monkeypatch) -> None:
    events = []
    server = FakeServer()
    server.command = "python"
    server.args = ["server.py"]

    class FakeStdioContext:
        async def __aenter__(self):
            events.append("stdio-enter")
            return object(), object()

        async def __aexit__(self, exc_type, exc, tb):
            events.append("stdio-exit")

    class FakeClientSession:
        def __init__(self, read_stream, write_stream) -> None:
            pass

        async def __aenter__(self):
            events.append("session-enter")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append("session-exit")

        async def initialize(self):
            raise asyncio.CancelledError()

    monkeypatch.setattr(
        mcp_runtime_module,
        "stdio_client",
        lambda params: FakeStdioContext(),
    )
    monkeypatch.setattr(mcp_runtime_module, "ClientSession", FakeClientSession)
    probe = StdioMcpProbe(
        allowed_commands={"python"},
        allowed_stdio_specs={"python:server.py"},
    )

    with pytest.raises(asyncio.CancelledError):
        await probe.start(server)

    assert events == [
        "stdio-enter",
        "session-enter",
        "session-exit",
        "stdio-exit",
    ]


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
    assert status.runtime_status == McpServerRuntimeStatus.stopped
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
async def test_live_check_success_restores_running_status_after_error() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FlakyListProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start(server.id)
    with pytest.raises(RuntimeError):
        await manager.check(server.id)

    status = await manager.check(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.running
    assert server.runtime_status == McpServerRuntimeStatus.running.value
    assert server.last_error is None


@pytest.mark.asyncio
async def test_start_existing_handle_restores_running_status_after_error() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FlakyListProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start(server.id)
    with pytest.raises(RuntimeError):
        await manager.check(server.id)

    status = await manager.start(server.id)

    assert status.runtime_status == McpServerRuntimeStatus.running
    assert server.runtime_status == McpServerRuntimeStatus.running.value
    assert server.last_error is None


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


@pytest.mark.asyncio
async def test_shutdown_stop_failure_keeps_handle() -> None:
    server = FakeServer()
    repository = FakeRepository(server)
    probe = FailingStopProbe()
    manager = McpRuntimeManager(repository_factory=lambda: repository, probe=probe)

    await manager.start(server.id)
    await manager.shutdown()

    assert manager.is_running(server.id) is True
    assert server.runtime_status == McpServerRuntimeStatus.error.value

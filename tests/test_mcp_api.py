import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_mcp_repository, get_mcp_runtime_manager
from app.core.config import settings
from app import main as main_module
from app.schemas.mcp import McpLifecycleResponse
from app.services.mcp_runtime import McpRuntimeNotEnabledError

app = main_module.app


class FakeTool:
    name = "search"
    description = "Search"
    input_schema = {"type": "object"}
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
        self.headers = {"Authorization": "Bearer secret"}
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
        self.committed = False
        self.raise_integrity_on_create = False
        self.raise_integrity_on_update = False

    async def list_servers(self):
        return [self.server]

    async def get_server(self, server_id):
        return self.server if server_id == self.server.id else None

    async def reload_server(self, server_id):
        return self.server if server_id == self.server.id else None

    async def create_server(self, **values):
        if self.raise_integrity_on_create:
            raise IntegrityError("insert", {}, Exception("duplicate"))
        for key, value in values.items():
            setattr(self.server, key, value)
        self.server.runtime_status = "unknown"
        self.server.tools = []
        return self.server

    async def update_server(self, server_id, **values):
        if self.raise_integrity_on_update:
            raise IntegrityError("update", {}, Exception("duplicate"))
        for key, value in values.items():
            setattr(self.server, key, value)
        return self.server

    async def delete_server(self, server_id):
        self.deleted = True

    async def commit(self):
        self.committed = True


class FakeRuntimeManager:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.started = []
        self.stopped = []
        self.running_ids = set()
        self.start_error: Exception | None = None
        self._lock = asyncio.Lock()
        self.lock_entries = 0

    async def start(self, server_id):
        if self.start_error is not None:
            raise self.start_error
        self.started.append(server_id)
        self.running_ids.add(server_id)
        self.repository.server.runtime_status = "running"
        self.repository.server.last_checked_at = datetime.now(UTC)
        self.repository.server.last_error = None
        self.repository.server.tools = [FakeTool()]
        return _lifecycle_response(server_id)

    async def stop(self, server_id):
        self.stopped.append(server_id)
        self.running_ids.discard(server_id)
        return _lifecycle_response(server_id, desired_state="stopped")

    async def stop_locked(self, server_id):
        return await self.stop(server_id)

    async def restart(self, server_id):
        return _lifecycle_response(server_id)

    async def check(self, server_id):
        return _lifecycle_response(server_id)

    def is_running(self, server_id):
        return server_id in self.running_ids

    @asynccontextmanager
    async def server_operation_lock(self, server_id):
        self.lock_entries += 1
        async with self._lock:
            yield


def _lifecycle_response(
    server_id,
    *,
    desired_state: str = "running",
) -> McpLifecycleResponse:
    return McpLifecycleResponse(
        server_id=server_id,
        desired_state=desired_state,
        runtime_status="running",
        last_checked_at=datetime.now(UTC),
        last_error=None,
        tool_count=1,
    )


@pytest.fixture(autouse=True)
def overrides():
    server = FakeServer()
    repository = FakeRepository(server)
    runtime = FakeRuntimeManager(repository)
    app.dependency_overrides[get_mcp_repository] = lambda: repository
    app.dependency_overrides[get_mcp_runtime_manager] = lambda: runtime
    yield server, repository, runtime
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_routes_reject_normal_user(monkeypatch, overrides) -> None:
    async def resolve_common_user(_request):
        return SimpleNamespace(account="common", is_admin=False)

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(main_module, "resolve_current_user", resolve_common_user)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/mcp/servers")

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required."}


@pytest.mark.asyncio
async def test_mcp_routes_allow_admin_user_without_token(
    monkeypatch,
    overrides,
) -> None:
    async def resolve_admin_user(_request):
        return SimpleNamespace(account="admin", is_admin=True)

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(main_module, "resolve_current_user", resolve_admin_user)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/mcp/servers")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_mcp_servers_redacts_env_and_counts_tools(overrides) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/mcp/servers")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["env"] == {"TOKEN": "********"}
    assert body[0]["headers"] == {"Authorization": "********"}
    assert body[0]["tool_count"] == 1


@pytest.mark.asyncio
async def test_get_mcp_server_returns_tools(overrides) -> None:
    server, _, _ = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/mcp/servers/{server.id}",
        )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_count"] == 1
    assert body["tools"][0]["name"] == "search"


@pytest.mark.asyncio
async def test_create_mcp_server_persists_and_redacts_response(overrides) -> None:
    _, repository, runtime = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/mcp/servers",
            json={
                "name": "github",
                "transport": "stdio",
                "command": "uvx",
                "args": ["mcp-server-github"],
                "env": {"TOKEN": "secret"},
                "headers": {},
                "enabled": False,
                "desired_state": "stopped",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "github"
    assert body["env"] == {"TOKEN": "********"}
    assert repository.committed is True
    assert runtime.started == []


@pytest.mark.asyncio
async def test_create_running_mcp_server_starts_and_returns_tools(overrides) -> None:
    server, _, runtime = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/mcp/servers",
            json={
                "name": "github",
                "transport": "stdio",
                "command": "uvx",
                "args": ["mcp-server-github"],
                "env": {"TOKEN": "secret"},
                "headers": {},
                "enabled": True,
                "desired_state": "running",
            },
        )

    assert response.status_code == 201
    assert runtime.started == [server.id]
    body = response.json()
    assert body["runtime_status"] == "running"
    assert body["tool_count"] == 1
    assert body["tools"][0]["name"] == "search"


@pytest.mark.asyncio
async def test_create_duplicate_mcp_server_name_returns_conflict(overrides) -> None:
    _, repository, _ = overrides
    repository.raise_integrity_on_create = True
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/mcp/servers",
            json={
                "name": "filesystem",
                "transport": "stdio",
                "command": "uvx",
            },
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_running_mcp_server_returns_conflict(overrides) -> None:
    server, _, _ = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/mcp/servers/{server.id}",
            json={"command": "node"},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_live_handle_returns_conflict_even_when_status_is_error(
    overrides,
) -> None:
    server, _, runtime = overrides
    server.runtime_status = "error"
    runtime.running_ids.add(server.id)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/mcp/servers/{server.id}",
            json={"command": "node"},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_stopped_mcp_server_validates_merged_config(overrides) -> None:
    server, _, _ = overrides
    server.runtime_status = "stopped"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/mcp/servers/{server.id}",
            json={"command": "   "},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_stopped_mcp_server_normalizes_config(overrides) -> None:
    server, repository, runtime = overrides
    server.runtime_status = "stopped"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/mcp/servers/{server.id}",
            json={"command": " node "},
        )

    assert response.status_code == 200
    assert response.json()["command"] == "node"
    assert server.command == "node"
    assert repository.committed is True
    assert runtime.started == [server.id]


@pytest.mark.asyncio
async def test_update_waits_for_mcp_lifecycle_lock(overrides) -> None:
    server, _, runtime = overrides
    server.runtime_status = "stopped"
    await runtime._lock.acquire()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        request_task = asyncio.create_task(
            client.patch(
                f"/api/mcp/servers/{server.id}",
                json={"command": "node"},
            )
        )
        await asyncio.sleep(0)
        assert request_task.done() is False

        runtime._lock.release()
        response = await request_task

    assert response.status_code == 200
    assert runtime.lock_entries == 1


@pytest.mark.asyncio
async def test_update_stopped_mcp_server_can_clear_nullable_config(
    overrides,
) -> None:
    server, repository, _ = overrides
    server.runtime_status = "stopped"
    server.url = "https://example.com/mcp"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/mcp/servers/{server.id}",
            json={"url": None},
        )

    assert response.status_code == 200
    assert response.json()["url"] is None
    assert server.url is None
    assert repository.committed is True


@pytest.mark.asyncio
async def test_start_mcp_server_returns_runtime_status(overrides) -> None:
    server, _, runtime = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/mcp/servers/{server.id}/start",
        )

    assert response.status_code == 200
    assert response.json()["runtime_status"] == "running"
    assert runtime.started == [server.id]


@pytest.mark.asyncio
async def test_start_mcp_server_failure_returns_bad_gateway(overrides) -> None:
    server, _, runtime = overrides
    runtime.start_error = RuntimeError("token=secret")
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/mcp/servers/{server.id}/start",
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "MCP lifecycle operation failed: token=[redacted]"
    assert "secret" not in response.text


@pytest.mark.asyncio
async def test_start_mcp_server_without_runtime_confirmation_returns_unavailable(
    overrides,
) -> None:
    server, _, runtime = overrides
    runtime.start_error = McpRuntimeNotEnabledError()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/mcp/servers/{server.id}/start",
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_delete_running_mcp_server_stops_then_deletes(overrides) -> None:
    server, repository, runtime = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(
            f"/api/mcp/servers/{server.id}",
        )

    assert response.status_code == 204
    assert runtime.stopped == [server.id]
    assert repository.deleted is True


@pytest.mark.asyncio
async def test_delete_live_handle_stops_even_when_status_is_error(overrides) -> None:
    server, repository, runtime = overrides
    server.runtime_status = "error"
    runtime.running_ids.add(server.id)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(
            f"/api/mcp/servers/{server.id}",
        )

    assert response.status_code == 204
    assert runtime.stopped == [server.id]
    assert repository.deleted is True


@pytest.mark.asyncio
async def test_delete_waits_for_mcp_lifecycle_lock(overrides) -> None:
    server, repository, runtime = overrides
    server.runtime_status = "stopped"
    await runtime._lock.acquire()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        request_task = asyncio.create_task(
            client.delete(
                f"/api/mcp/servers/{server.id}",
            )
        )
        await asyncio.sleep(0)
        assert request_task.done() is False

        runtime._lock.release()
        response = await request_task

    assert response.status_code == 204
    assert repository.deleted is True
    assert runtime.lock_entries == 1

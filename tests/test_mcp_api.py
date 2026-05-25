from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_mcp_repository, get_mcp_runtime_manager
from app.main import app
from app.schemas.mcp import McpLifecycleResponse


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

    async def list_servers(self):
        return [self.server]

    async def get_server(self, server_id):
        return self.server if server_id == self.server.id else None

    async def create_server(self, **values):
        for key, value in values.items():
            setattr(self.server, key, value)
        self.server.runtime_status = "unknown"
        self.server.tools = []
        return self.server

    async def update_server(self, server_id, **values):
        for key, value in values.items():
            if value is not None:
                setattr(self.server, key, value)
        return self.server

    async def delete_server(self, server_id):
        self.deleted = True

    async def commit(self):
        self.committed = True


class FakeRuntimeManager:
    def __init__(self) -> None:
        self.started = []
        self.stopped = []

    async def start(self, server_id):
        self.started.append(server_id)
        return _lifecycle_response(server_id)

    async def stop(self, server_id):
        self.stopped.append(server_id)
        return _lifecycle_response(server_id, desired_state="stopped")

    async def restart(self, server_id):
        return _lifecycle_response(server_id)

    async def check(self, server_id):
        return _lifecycle_response(server_id)


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
    runtime = FakeRuntimeManager()
    app.dependency_overrides[get_mcp_repository] = lambda: repository
    app.dependency_overrides[get_mcp_runtime_manager] = lambda: runtime
    yield server, repository, runtime
    app.dependency_overrides.clear()


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
        response = await client.get(f"/api/mcp/servers/{server.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["tool_count"] == 1
    assert body["tools"][0]["name"] == "search"


@pytest.mark.asyncio
async def test_create_mcp_server_persists_and_redacts_response(overrides) -> None:
    _, repository, _ = overrides
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
    server, repository, _ = overrides
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


@pytest.mark.asyncio
async def test_start_mcp_server_returns_runtime_status(overrides) -> None:
    server, _, runtime = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(f"/api/mcp/servers/{server.id}/start")

    assert response.status_code == 200
    assert response.json()["runtime_status"] == "running"
    assert runtime.started == [server.id]


@pytest.mark.asyncio
async def test_delete_running_mcp_server_stops_then_deletes(overrides) -> None:
    server, repository, runtime = overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(f"/api/mcp/servers/{server.id}")

    assert response.status_code == 204
    assert runtime.stopped == [server.id]
    assert repository.deleted is True

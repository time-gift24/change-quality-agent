from app.api import deps
from app.api.deps import get_mcp_repository, get_mcp_runtime_manager
from app.repositories.mcp_servers import McpServerRepository
from app.services.mcp_runtime import McpRuntimeManager, TaskOwnedMcpProbe, TransportMcpProbe


def test_mcp_repository_dependency_uses_session() -> None:
    session = object()

    repository = get_mcp_repository(session)

    assert isinstance(repository, McpServerRepository)
    assert repository._session is session


def test_mcp_runtime_manager_singleton() -> None:
    first = get_mcp_runtime_manager()
    second = get_mcp_runtime_manager()

    assert isinstance(first, McpRuntimeManager)
    assert first is second


def test_mcp_runtime_manager_uses_transport_probe(monkeypatch) -> None:
    monkeypatch.setattr(deps, "_mcp_runtime_manager", None)

    manager = get_mcp_runtime_manager()

    assert isinstance(manager._probe, TaskOwnedMcpProbe)
    assert isinstance(manager._probe.inner_probe, TransportMcpProbe)

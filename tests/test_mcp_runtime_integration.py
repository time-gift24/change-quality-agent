import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.mcp import McpDesiredState, McpServerRuntimeStatus
from app.services.mcp_runtime import McpRuntimeManager, StdioMcpProbe


class IntegrationRepository:
    def __init__(self, server: SimpleNamespace) -> None:
        self.server = server
        self.tools: list[dict] = []
        self.commits = 0

    async def require_server(self, server_id: object) -> object:
        assert server_id == self.server.id
        return self.server

    async def update_desired_state(
        self, server_id: object, desired_state: object
    ) -> object:
        assert server_id == self.server.id
        self.server.desired_state = desired_state
        return self.server

    async def update_runtime_status(
        self,
        server_id: object,
        *,
        runtime_status: object,
        last_error: object = None,
        checked: object = False,
    ) -> object:
        assert server_id == self.server.id
        self.server.runtime_status = runtime_status
        self.server.last_error = last_error
        if checked:
            self.server.last_checked_at = datetime.now(UTC)
        return self.server

    async def replace_tools(self, server_id: object, tools: object) -> object:
        assert server_id == self.server.id
        self.tools = tools
        self.server.tools = tools
        return []

    async def tool_count(self, server_id: object) -> object:
        assert server_id == self.server.id
        return len(self.tools)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_stdio_probe_discovers_tools_from_real_mcp_server() -> None:
    server_script = Path(__file__).parent / "fixtures" / "mcp_echo_server.py"
    assert server_script.exists()
    server = SimpleNamespace(
        id=uuid4(),
        name="echo",
        transport="stdio",
        command=sys.executable,
        args=[str(server_script)],
        env={},
        desired_state=McpDesiredState.stopped.value,
        runtime_status=McpServerRuntimeStatus.unknown.value,
        last_checked_at=None,
        last_error=None,
        tools=[],
    )
    repository = IntegrationRepository(server)
    manager = McpRuntimeManager(
        repository_factory=lambda: repository,
        probe=StdioMcpProbe(
            allowed_commands={sys.executable},
            allowed_stdio_specs={f"{sys.executable}:{server_script}"},
        ),
    )

    try:
        status = await manager.start(server.id)

        assert status.runtime_status == McpServerRuntimeStatus.running
        assert status.desired_state == McpDesiredState.running
        assert status.tool_count == 1
        assert repository.tools[0]["name"] == "echo_path"
        assert "path" in repository.tools[0]["input_schema"]["properties"]
        assert server.last_checked_at is not None
    finally:
        await manager.shutdown()

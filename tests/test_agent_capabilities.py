from uuid import uuid4

import pytest

from app.services.agent_capabilities import (
    BUILTIN_AGENT_TOOLS,
    AgentCapabilityService,
    UnknownBuiltinToolError,
)


class FakeMcpServer:
    def __init__(
        self,
        *,
        server_id,
        name="Docs MCP",
        enabled=True,
        status="running",
        tools=None,
    ):
        self.id = server_id
        self.name = name
        self.enabled = enabled
        self.runtime_status = status
        self.tools = tools or [object(), object()]


class FakeMcpRepository:
    def __init__(self, servers):
        self._servers = servers

    async def list_servers(self):
        return list(self._servers)


@pytest.mark.asyncio
async def test_capability_service_lists_builtin_tools_and_mcp_servers():
    server_id = uuid4()
    service = AgentCapabilityService(
        mcp_repository=FakeMcpRepository(
            [
                FakeMcpServer(server_id=server_id, tools=[object()]),
            ]
        ),
    )

    result = await service.list_capabilities()

    assert result.builtin_tools
    assert result.builtin_tools[0].name == BUILTIN_AGENT_TOOLS[0].name
    assert result.mcp_servers[0].id == str(server_id)
    assert result.mcp_servers[0].tool_count == 1


def test_capability_service_rejects_unknown_builtin_tool():
    service = AgentCapabilityService(mcp_repository=FakeMcpRepository([]))

    with pytest.raises(UnknownBuiltinToolError):
        service.resolve_builtin_tools(["missing-tool"])

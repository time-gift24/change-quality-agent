from dataclasses import dataclass
from typing import Protocol

from langchain_core.tools import tool

from app.schemas.agents import (
    AgentCapabilities,
    BuiltinAgentToolCapability,
    McpAgentCapability,
)


class UnknownBuiltinToolError(ValueError):
    pass


@dataclass(frozen=True)
class BuiltinAgentTool:
    name: str
    label: str
    description: str | None
    enabled: bool = True
    implementation: object | None = None


@tool("echo")
def echo_tool(text: str) -> str:
    """Echo text back to the caller for local Agent testing."""
    return text


BUILTIN_AGENT_TOOLS: tuple[BuiltinAgentTool, ...] = (
    BuiltinAgentTool(
        name="echo",
        label="Echo",
        description="Echoes input text. Useful for validating Agent tool wiring.",
        implementation=echo_tool,
    ),
)


class McpRepositoryLike(Protocol):
    async def list_servers(self) -> list[object]: ...


class AgentCapabilityService:
    def __init__(self, *, mcp_repository: McpRepositoryLike) -> None:
        self._mcp_repository = mcp_repository

    async def list_capabilities(self) -> AgentCapabilities:
        servers = await self._mcp_repository.list_servers()
        return AgentCapabilities(
            builtin_tools=[
                BuiltinAgentToolCapability(
                    name=item.name,
                    label=item.label,
                    description=item.description,
                    enabled=item.enabled,
                )
                for item in BUILTIN_AGENT_TOOLS
            ],
            mcp_servers=[
                McpAgentCapability(
                    id=str(server.id),
                    name=server.name,
                    enabled=bool(server.enabled),
                    runtime_status=str(server.runtime_status),
                    tool_count=len(getattr(server, "tools", []) or []),
                )
                for server in servers
            ],
        )

    def resolve_builtin_tools(self, names: list[str]) -> list[object]:
        registry = {item.name: item for item in BUILTIN_AGENT_TOOLS if item.enabled}
        tools: list[object] = []
        for name in names:
            item = registry.get(name)
            if item is None or item.implementation is None:
                raise UnknownBuiltinToolError(name)
            tools.append(item.implementation)
        return tools

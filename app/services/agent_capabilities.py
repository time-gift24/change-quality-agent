from dataclasses import dataclass
import json
import re
from typing import Protocol
from uuid import UUID

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, Field, create_model

from app.core.config import settings
from app.core.json_types import JsonObject, to_json_object
from app.core.llm_models import CODEAGENT_MODEL_PREFIX
from app.schemas.agents import (
    AgentCapabilities,
    BuiltinAgentToolCapability,
    McpAgentCapability,
)


class UnknownBuiltinToolError(ValueError):
    pass


class UnknownMcpServerError(ValueError):
    pass


class UnavailableMcpServerError(RuntimeError):
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


class McpRuntimeLike(Protocol):
    def is_running(self, server_id: UUID) -> bool: ...

    async def call_tool(
        self,
        server_id: UUID,
        tool_name: str,
        arguments: JsonObject,
    ) -> object: ...


class AgentCapabilityService:
    def __init__(self, *, mcp_repository: McpRepositoryLike) -> None:
        self._mcp_repository = mcp_repository

    async def list_capabilities(self) -> AgentCapabilities:
        servers = await self._mcp_repository.list_servers()
        return AgentCapabilities(
            codeagent_models=list_codeagent_models(),
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

    async def resolve_mcp_tools(
        self,
        server_ids: list[str],
        runtime: McpRuntimeLike,
    ) -> list[object]:
        if not server_ids:
            return []

        servers = {str(server.id): server for server in await self._mcp_repository.list_servers()}
        tools: list[object] = []
        for server_id in server_ids:
            server = servers.get(server_id)
            if server is None:
                raise UnknownMcpServerError(server_id)
            if not bool(server.enabled):
                raise UnavailableMcpServerError(f"MCP server is disabled: {server_id}")
            server_uuid = UUID(server_id)
            if not runtime.is_running(server_uuid):
                raise UnavailableMcpServerError(
                    f"MCP server runtime is not running: {server_id}"
                )
            server_tools = list(getattr(server, "tools", []) or [])
            if not server_tools:
                raise UnavailableMcpServerError(
                    f"MCP server has no discovered tools: {server_id}"
                )
            for server_tool in server_tools:
                tools.append(_build_mcp_tool(server, server_tool, runtime))
        return tools


def list_codeagent_models() -> list[str]:
    if not settings.codeagent_base_url:
        return []
    models: list[str] = []
    for raw_model in settings.codeagent_models:
        model = raw_model.strip()
        if not model:
            continue
        models.append(
            model
            if model.startswith(CODEAGENT_MODEL_PREFIX)
            else f"{CODEAGENT_MODEL_PREFIX}{model}"
        )
    return models


def _build_mcp_tool(
    server: object,
    server_tool: object,
    runtime: McpRuntimeLike,
) -> StructuredTool:
    server_id = UUID(str(server.id))
    mcp_tool_name = str(server_tool.name)
    args_schema = _schema_to_model(
        f"Mcp{server_id.hex[:8]}{_python_identifier(mcp_tool_name)}Input",
        getattr(server_tool, "input_schema", {}) or {},
    )

    async def call_mcp_tool(**kwargs: object) -> str:
        result = await runtime.call_tool(
            server_id,
            mcp_tool_name,
            to_json_object(dict(kwargs)),
        )
        return _serialize_mcp_result(result)

    return StructuredTool.from_function(
        coroutine=call_mcp_tool,
        name=f"mcp_{server_id.hex[:8]}_{_tool_name(mcp_tool_name)}",
        description=(
            f"{getattr(server_tool, 'description', None) or mcp_tool_name} "
            f"(MCP server: {getattr(server, 'name', server_id)})"
        ),
        args_schema=args_schema,
    )


def _schema_to_model(name: str, schema: JsonObject) -> type[BaseModel]:
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict):
        properties = {}
    required_names = set(required if isinstance(required, list) else [])

    fields: dict[str, tuple[object, object]] = {}
    for raw_field_name, raw_field_schema in properties.items():
        if not isinstance(raw_field_name, str):
            continue
        field_name = _python_identifier(raw_field_name)
        field_schema = raw_field_schema if isinstance(raw_field_schema, dict) else {}
        field_type = _json_schema_type(field_schema)
        default = ... if raw_field_name in required_names else None
        fields[field_name] = (
            field_type if default is ... else field_type | None,
            Field(default, description=field_schema.get("description")),
        )

    if not fields:
        return create_model(name)
    return create_model(name, **fields)


def _json_schema_type(schema: JsonObject) -> type[object]:
    schema_type = schema.get("type")
    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list
    if schema_type == "object":
        return dict
    return object


def _tool_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    return name or "tool"


def _python_identifier(value: str) -> str:
    name = re.sub(r"\W+", "_", value).strip("_")
    if not name:
        return "value"
    if name[0].isdigit():
        return f"value_{name}"
    return name


def _serialize_mcp_result(result: object) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
            else:
                parts.append(json.dumps(_jsonable(item), ensure_ascii=False))
        return "\n".join(parts)
    return json.dumps(_jsonable(result), ensure_ascii=False)


def _jsonable(value: object) -> object:
    model_dump = getattr(value, "model_dump", None)
    if model_dump is not None:
        return model_dump(mode="json")
    if isinstance(value, dict | list | str | int | float | bool) or value is None:
        return value
    return str(value)

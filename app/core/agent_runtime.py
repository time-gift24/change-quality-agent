import inspect
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from langchain.agents import create_agent as langchain_create_agent

from app.core.json_types import JsonObject, JsonValue
from app.core.llm_model_config import (
    LlmModelParameters,
    dump_llm_model_parameters,
)
from app.core.llm_models import (
    LlmProviderRuntimeConfig,
    create_chat_model,
    create_provider_chat_model,
)
from app.core.stream_events import runtime_stream_event


@dataclass(frozen=True)
class AgentRuntimeResult:
    messages: list[JsonObject]
    raw_output: JsonObject


class StaticToolResolver:
    def resolve(
        self,
        tool_allowlist: list[str],
        mcp_server_ids: list[str],
    ) -> list[object]:
        return []


class _CapabilityServiceLike(Protocol):
    def resolve_builtin_tools(self, names: list[str]) -> list[object]: ...

    async def resolve_mcp_tools(
        self,
        server_ids: list[str],
        runtime: object,
    ) -> list[object]: ...


class CapabilityToolResolver:
    """Tool resolver that uses `AgentCapabilityService` for built-in tools.

    """

    def __init__(
        self,
        *,
        capability_service: _CapabilityServiceLike,
        mcp_runtime: object | None = None,
    ) -> None:
        self._capability_service = capability_service
        self._mcp_runtime = mcp_runtime

    async def resolve(
        self,
        tool_allowlist: list[str],
        mcp_server_ids: list[str],
    ) -> list[object]:
        builtin = self._capability_service.resolve_builtin_tools(list(tool_allowlist))
        if not mcp_server_ids:
            return list(builtin)
        if self._mcp_runtime is None:
            raise RuntimeError("MCP runtime is not configured.")
        mcp_tools = await self._capability_service.resolve_mcp_tools(
            list(mcp_server_ids),
            self._mcp_runtime,
        )
        return [*builtin, *mcp_tools]


class LlmProviderResolver(Protocol):
    async def resolve(self, provider_id: UUID) -> LlmProviderRuntimeConfig:
        pass


class AgentVersionLike(Protocol):
    model: str
    system_prompt: str
    provider_id: UUID | None
    model_config: LlmModelParameters | Mapping[str, object] | None
    tool_allowlist: list[str]
    mcp_server_ids: list[str]


class AgentRuntime:
    def __init__(
        self,
        create_agent=langchain_create_agent,
        tool_resolver: StaticToolResolver | None = None,
        *,
        model_factory=create_chat_model,
        provider_resolver: LlmProviderResolver | None = None,
        provider_model_factory=create_provider_chat_model,
    ) -> None:
        self._create_agent = create_agent
        self._tool_resolver = tool_resolver or StaticToolResolver()
        self._model_factory = model_factory
        self._provider_resolver = provider_resolver
        self._provider_model_factory = provider_model_factory

    async def run(
        self,
        *,
        version: AgentVersionLike,
        messages: list[JsonObject],
    ) -> AgentRuntimeResult:
        agent = await self._build_agent(version)
        raw_output = await self._invoke(agent, {"messages": messages})
        output = to_jsonable(raw_output) if isinstance(raw_output, Mapping) else {}
        return AgentRuntimeResult(
            messages=_extract_messages(output),
            raw_output=output,
        )

    async def stream(
        self,
        *,
        version: AgentVersionLike,
        messages: list[JsonObject],
    ):
        agent = await self._build_agent(version)
        payload = {"messages": messages}

        astream = getattr(agent, "astream", None)
        if astream is None:
            raw_output = await self._invoke(agent, payload)
            output = to_jsonable(raw_output) if isinstance(raw_output, Mapping) else {}
            yield {
                "type": "messages",
                "node": "agent",
                "payload": {
                    "final": True,
                    "messages": _extract_messages(output),
                },
            }
            return

        stream = astream(
            payload,
            stream_mode=["messages", "updates", "custom"],
        )
        if inspect.isawaitable(stream):
            stream = await stream

        async for chunk_type, chunk in stream:
            yield runtime_stream_event(chunk_type, chunk)

    async def _build_agent(self, version: AgentVersionLike) -> object:
        tools = self._tool_resolver.resolve(
            list(getattr(version, "tool_allowlist", [])),
            list(getattr(version, "mcp_server_ids", [])),
        )
        if inspect.isawaitable(tools):
            tools = await tools
        model_config = dump_llm_model_parameters(
            getattr(version, "model_config", None)
        )
        provider_id = getattr(version, "provider_id", None)
        if provider_id:
            if self._provider_resolver is None:
                raise RuntimeError("LLM provider resolver is not configured.")
            provider = await self._provider_resolver.resolve(provider_id)
            model = self._provider_model_factory(
                version.model,
                provider,
                **model_config,
            )
        else:
            model = self._model_factory(version.model, **model_config)
        agent = self._create_agent(
            model=model,
            tools=tools,
            system_prompt=version.system_prompt,
        )
        return agent

    async def _invoke(self, agent: object, payload: JsonObject) -> object:
        invoke = getattr(agent, "ainvoke", None)
        if invoke is not None:
            result = invoke(payload)
            if inspect.isawaitable(result):
                return await result
            return result

        invoke = getattr(agent, "invoke", None)
        if invoke is None:
            raise TypeError("Agent does not support invoke or ainvoke.")

        result = invoke(payload)
        if inspect.isawaitable(result):
            return await result
        return result


def to_jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value

    if isinstance(value, Mapping):
        return {_json_key(key): to_jsonable(item) for key, item in value.items()}

    if isinstance(value, list | tuple | set | frozenset):
        return [to_jsonable(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if model_dump is not None:
        try:
            return to_jsonable(model_dump(mode="json"))
        except TypeError:
            return to_jsonable(model_dump())

    to_dict = getattr(value, "dict", None)
    if to_dict is not None:
        return to_jsonable(to_dict())

    if isinstance(value, bytes):
        return value.decode(errors="replace")

    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value


def _json_key(key: object) -> str:
    if isinstance(key, str):
        return key
    return str(to_jsonable(key))


def _extract_messages(output: JsonObject) -> list[JsonObject]:
    messages = output.get("messages", [])
    if not isinstance(messages, list):
        return []
    return [_message_to_dict(message) for message in messages]


def _message_to_dict(message: object) -> JsonObject:
    converted = to_jsonable(message)
    if isinstance(converted, Mapping):
        return dict(converted)
    return {"content": str(converted)}

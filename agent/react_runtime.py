import inspect
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent as langchain_create_agent
from langchain.chat_models import init_chat_model


@dataclass(frozen=True)
class AgentRunResult:
    messages: list[dict[str, Any]]
    raw_output: dict[str, Any]


class StaticToolResolver:
    def resolve(
        self,
        tool_allowlist: list[str],
        mcp_server_ids: list[str],
    ) -> list[Any]:
        return []


class AgentRuntime:
    def __init__(
        self,
        create_agent=langchain_create_agent,
        tool_resolver: StaticToolResolver | None = None,
        *,
        model_factory=init_chat_model,
    ) -> None:
        self._create_agent = create_agent
        self._tool_resolver = tool_resolver or StaticToolResolver()
        self._model_factory = model_factory

    async def run(
        self,
        *,
        version: Any,
        messages: list[dict[str, Any]],
    ) -> AgentRunResult:
        tools = self._tool_resolver.resolve(
            list(getattr(version, "tool_allowlist", [])),
            list(getattr(version, "mcp_server_ids", [])),
        )
        if inspect.isawaitable(tools):
            tools = await tools
        model_config = getattr(version, "model_config", {}) or {}
        model = self._model_factory(version.model, **dict(model_config))
        agent = self._create_agent(
            model=model,
            tools=tools,
            system_prompt=version.system_prompt,
        )
        raw_output = await self._invoke(agent, {"messages": messages})
        output = to_jsonable(raw_output) if isinstance(raw_output, Mapping) else {}
        return AgentRunResult(
            messages=_extract_messages(output),
            raw_output=output,
        )

    async def _invoke(self, agent: Any, payload: dict[str, Any]) -> Any:
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


def to_jsonable(value: Any) -> Any:
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


def _json_key(key: Any) -> str:
    if isinstance(key, str):
        return key
    return str(to_jsonable(key))


def _extract_messages(output: dict[str, Any]) -> list[dict[str, Any]]:
    messages = output.get("messages", [])
    if not isinstance(messages, list):
        return []
    return [_message_to_dict(message) for message in messages]


def _message_to_dict(message: Any) -> dict[str, Any]:
    converted = to_jsonable(message)
    if isinstance(converted, Mapping):
        return dict(converted)
    return {"content": str(converted)}

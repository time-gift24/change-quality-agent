import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent as langchain_create_agent


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
    ) -> None:
        self._create_agent = create_agent
        self._tool_resolver = tool_resolver or StaticToolResolver()

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
        agent = self._create_agent(
            model=version.model,
            tools=tools,
            system_prompt=version.system_prompt,
        )
        raw_output = await self._invoke(agent, {"messages": messages})
        output = dict(raw_output) if isinstance(raw_output, Mapping) else {}
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


def _extract_messages(output: dict[str, Any]) -> list[dict[str, Any]]:
    messages = output.get("messages", [])
    if not isinstance(messages, list):
        return []
    return [_message_to_dict(message) for message in messages]


def _message_to_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, Mapping):
        return dict(message)

    model_dump = getattr(message, "model_dump", None)
    if model_dump is not None:
        try:
            return dict(model_dump(mode="json"))
        except TypeError:
            return dict(model_dump())

    to_dict = getattr(message, "dict", None)
    if to_dict is not None:
        return dict(to_dict())

    return {"content": str(message)}

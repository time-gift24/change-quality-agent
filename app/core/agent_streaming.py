"""Runtime layer for streaming DeepAgent execution into session transcripts."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from langchain_core.messages import BaseMessage

from app.core.json_types import JsonObject


@dataclass
class DeepAgentRunInput:
    """Input payload for a single DeepAgent step run."""

    messages: list[JsonObject] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass
class DeepAgentRunResult:
    """Output of a single DeepAgent step run."""

    final_text: str
    metadata: JsonObject = field(default_factory=dict)


class SessionMessageWriter(Protocol):
    """Narrow writer protocol used by graph nodes and runners."""

    async def append_step_message(
        self,
        *,
        step: str,
        role: str,
        content: str,
        additional_kwargs: JsonObject | None = None,
    ) -> object:
        ...


LiveEventPublisher = Callable[[JsonObject], Awaitable[None]]


class DeepAgentStreamRunner:
    """Runs a DeepAgent step, streaming deltas live and persisting the final message."""

    def __init__(
        self,
        *,
        message_writer: SessionMessageWriter,
        live_event_publisher: LiveEventPublisher | None = None,
        session_id: int | None = None,
    ) -> None:
        self._writer = message_writer
        self._publisher = live_event_publisher
        self._session_id = session_id

    async def run_step(
        self,
        *,
        agent: object,
        step: str,
        input: DeepAgentRunInput,
    ) -> DeepAgentRunResult:
        payload = {"messages": list(input.messages)}
        astream = getattr(agent, "astream", None)

        if astream is None:
            final_text = await self._run_invoke(agent, payload)
        else:
            final_text = await self._run_astream(astream, payload, step=step)

        await self._writer.append_step_message(
            step=step,
            role="assistant",
            content=final_text,
            additional_kwargs={"kind": "final_message", "step": step},
        )
        return DeepAgentRunResult(final_text=final_text)

    async def _run_astream(
        self,
        astream: Callable[..., object],
        payload: JsonObject,
        *,
        step: str,
    ) -> str:
        chunks: list[str] = []
        thinking_published = False

        stream = astream(payload, stream_mode=["messages", "updates", "custom"])
        async for chunk_type, chunk in stream:
            if chunk_type != "messages":
                continue
            message = chunk[0] if _is_tuple(chunk) else chunk

            if not thinking_published and _has_reasoning(message):
                thinking_published = True
                await self._publish(
                    {
                        "type": "message_delta",
                        "session_id": self._session_id,
                        "sequence": None,
                        "role": "assistant",
                        "content": "",
                        "additional_kwargs": {
                            "step": step,
                            "channel": "thinking",
                            "status": "started",
                        },
                    }
                )

            delta = _content_delta(message)
            if not delta:
                continue
            chunks.append(delta)
            await self._publish(
                {
                    "type": "message_delta",
                    "session_id": self._session_id,
                    "sequence": None,
                    "role": "assistant",
                    "content": delta,
                    "additional_kwargs": {"step": step, "channel": "content"},
                }
            )

        return "".join(chunks)

    async def _run_invoke(self, agent: object, payload: JsonObject) -> str:
        ainvoke = getattr(agent, "ainvoke", None)
        if ainvoke is not None:
            output = await ainvoke(payload)
            return _extract_text(output)

        invoke = getattr(agent, "invoke", None)
        if invoke is None:
            raise TypeError("Agent does not support astream, ainvoke, or invoke.")
        output = invoke(payload)
        return _extract_text(output)

    async def _publish(self, event: JsonObject) -> None:
        if self._publisher is None:
            return
        await self._publisher(event)


def _is_tuple(value: object) -> bool:
    return isinstance(value, tuple | list) and len(value) >= 1


def _content_delta(message: object) -> str:
    if isinstance(message, BaseMessage):
        content = message.content
        return content if isinstance(content, str) else ""
    if isinstance(message, dict):
        content = message.get("content")
        return content if isinstance(content, str) else ""
    content = getattr(message, "content", None)
    return content if isinstance(content, str) else ""


def _has_reasoning(message: object) -> bool:
    additional = None
    if isinstance(message, dict):
        additional = message.get("additional_kwargs")
    else:
        additional = getattr(message, "additional_kwargs", None)
    if not isinstance(additional, dict):
        return False
    for key in ("reasoning_content", "reasoning"):
        value = additional.get(key)
        if isinstance(value, str) and value:
            return True
    return False


def _extract_text(output: object) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        messages = output.get("messages")
        if isinstance(messages, list) and messages:
            return _message_text(messages[-1])
    if hasattr(output, "content"):
        return _message_text(output)
    raise ValueError("Agent did not return text output.")


def _message_text(message: object) -> str:
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""

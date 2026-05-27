import inspect
from collections.abc import AsyncIterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.core.agent_runtime import to_jsonable


@dataclass(frozen=True)
class RuntimeStreamResult:
    messages: list[dict[str, Any]]
    raw_graph_output: dict[str, Any]
    done_seen: bool
    error: dict[str, Any] | None = None


SUPPORTED_STREAM_EVENT_TYPES = {
    "tasks",
    "messages",
    "updates",
    "custom",
    "checkpoints",
    "error",
    "done",
}


async def consume_runtime_stream(
    repository: Any,
    run: Any,
    events: AsyncIterable[Any],
) -> RuntimeStreamResult:
    result_messages: list[dict[str, Any]] = []
    message_deltas: list[str] = []
    raw_events: list[Any] = []
    done_seen = False
    stream_error: dict[str, Any] | None = None

    async for event in events:
        json_event = to_jsonable(event)
        raw_events.append(json_event)
        event_parts = _stream_event_parts(json_event)
        if event_parts is None:
            continue

        await repository.append_event(
            run.id,
            event_type=event_parts["event_type"],
            thread_id=run.thread_id,
            payload=event_parts["payload"],
            node=event_parts["node"],
            checkpoint_id=event_parts["checkpoint_id"],
            task_id=event_parts["task_id"],
        )
        await _commit_if_available(repository)

        payload = event_parts["payload"]
        if event_parts["event_type"] == "done":
            done_seen = True
        if event_parts["event_type"] == "error":
            stream_error = _stream_error_payload(payload)
        if isinstance(payload.get("delta"), str):
            message_deltas.append(payload["delta"])
        if isinstance(payload.get("messages"), list):
            result_messages = to_jsonable(payload["messages"])

    if not result_messages and message_deltas:
        result_messages = [
            {"role": "assistant", "content": "".join(message_deltas)},
        ]

    return RuntimeStreamResult(
        messages=result_messages,
        raw_graph_output={"stream_events": raw_events},
        done_seen=done_seen,
        error=stream_error,
    )


async def _commit_if_available(repository: Any) -> None:
    commit = getattr(repository, "commit", None)
    if commit is None:
        return
    result = commit()
    if inspect.isawaitable(result):
        await result


def _stream_event_parts(event: Any) -> dict[str, Any] | None:
    if not isinstance(event, Mapping):
        return None

    event_type = event.get("type")
    payload = event.get("payload")
    if not isinstance(event_type, str) or not isinstance(payload, Mapping):
        return None
    if event_type not in SUPPORTED_STREAM_EVENT_TYPES:
        event_type = "custom"

    return {
        "event_type": event_type,
        "payload": dict(payload),
        "node": _optional_str(event.get("node")),
        "checkpoint_id": _optional_str(event.get("checkpoint_id")),
        "task_id": _optional_str(event.get("task_id")),
    }


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _stream_error_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    error = payload.get("error")
    source = error if isinstance(error, Mapping) else payload
    error_type = source.get("type")
    message = source.get("message")
    return {
        "type": error_type if isinstance(error_type, str) else "StreamError",
        "message": message if isinstance(message, str) else "Stream failed.",
    }

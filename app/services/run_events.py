from collections.abc import Mapping, Sequence
from typing import Any

SUPPORTED_EVENT_TYPES = {
    "tasks",
    "messages",
    "updates",
    "custom",
    "checkpoints",
    "error",
    "done",
}


def normalize_langgraph_chunk(
    *,
    chunk_type: str,
    chunk: object,
    run_id: str,
    thread_id: str,
    sequence: int,
) -> dict[str, object]:
    event_type = chunk_type if chunk_type in SUPPORTED_EVENT_TYPES else "custom"
    node = _extract_node(event_type, chunk)
    payload = _build_payload(event_type, chunk, node)
    metadata = _extract_metadata(chunk)

    return {
        "run_id": run_id,
        "thread_id": thread_id,
        "sequence": sequence,
        "type": event_type,
        "node": node,
        "checkpoint_id": _string_or_none(metadata.get("checkpoint_id")),
        "task_id": _string_or_none(metadata.get("task_id")),
        "payload": payload,
    }


def _build_payload(
    event_type: str,
    chunk: object,
    node: str | None,
) -> dict[str, Any]:
    if event_type == "updates" and node and isinstance(chunk, Mapping):
        return {"node": node, "update": _json_safe(chunk[node]), "raw": _json_safe(chunk)}
    if event_type == "error":
        return {"error": _json_safe(chunk), "raw": _json_safe(chunk)}
    if event_type == "done":
        return {"status": "done", "raw": _json_safe(chunk)}
    return {"raw": _json_safe(chunk)}


def _extract_node(event_type: str, chunk: object) -> str | None:
    metadata = _extract_metadata(chunk)
    for key in ("langgraph_node", "node"):
        value = metadata.get(key)
        if isinstance(value, str):
            return value

    if event_type == "updates" and isinstance(chunk, Mapping) and len(chunk) == 1:
        key = next(iter(chunk.keys()))
        if isinstance(key, str):
            return key

    if isinstance(chunk, Mapping):
        value = chunk.get("node")
        if isinstance(value, str):
            return value

    return None


def _extract_metadata(chunk: object) -> Mapping[str, object]:
    if _is_message_tuple(chunk):
        metadata = chunk[1]
        if isinstance(metadata, Mapping):
            return metadata
    if isinstance(chunk, Mapping):
        metadata = chunk.get("metadata")
        if isinstance(metadata, Mapping):
            return metadata
    return {}


def _is_message_tuple(chunk: object) -> bool:
    return isinstance(chunk, Sequence) and not isinstance(chunk, str | bytes) and len(chunk) >= 2


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _json_safe(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)

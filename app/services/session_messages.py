"""Persist DeepAgent step messages into a session transcript."""

import inspect
from collections.abc import Callable
from typing import Any, Protocol


class _SessionRepositoryLike(Protocol):
    async def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        ...


class _BroadcastLike(Protocol):
    async def publish(self, session_id: int, message: dict[str, Any]) -> None:
        ...


class RepositorySessionMessageWriter:
    """Append final step messages and broadcast persisted events."""

    def __init__(
        self,
        *,
        repository: _SessionRepositoryLike,
        session_id: int,
        broadcast: _BroadcastLike | None = None,
        commit: Callable[[], Any] | None = None,
    ) -> None:
        self._repository = repository
        self._session_id = session_id
        self._broadcast = broadcast
        self._commit = commit

    async def append_step_message(
        self,
        *,
        step: str,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        merged: dict[str, Any] = dict(additional_kwargs or {})
        merged["step"] = step

        message = await self._repository.append_message(
            self._session_id,
            role=role,
            content=content,
            additional_kwargs=merged,
        )

        if self._commit is not None:
            result = self._commit()
            if inspect.isawaitable(result):
                await result

        if self._broadcast is not None:
            await self._broadcast.publish(
                self._session_id,
                {"type": "message", **_message_to_dict(message)},
            )

        return message


def _message_to_dict(message: Any) -> dict[str, Any]:
    created_at = getattr(message, "created_at", None)
    return {
        "id": str(getattr(message, "id", "")),
        "session_id": getattr(message, "session_id", None),
        "sequence": getattr(message, "sequence", None),
        "role": getattr(message, "role", None),
        "content": getattr(message, "content", None),
        "additional_kwargs": dict(getattr(message, "additional_kwargs", {}) or {}),
        "created_at": created_at.isoformat()
        if hasattr(created_at, "isoformat")
        else created_at,
    }

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.repositories.sessions import SessionRepository
from app.services.session_streaming import SessionBroadcast

TERMINAL_SESSION_STATUSES = {"completed", "failed", "interrupted"}


class SessionNotFoundError(KeyError):
    pass


class SessionService:
    def __init__(
        self,
        *,
        repository: SessionRepository,
        broadcast: SessionBroadcast,
    ) -> None:
        self._repository = repository
        self._broadcast = broadcast

    async def get_session(self, session_id: int) -> object:
        runtime_session = await self._repository.get_session(session_id)
        if runtime_session is None:
            raise SessionNotFoundError(session_id)
        return runtime_session

    async def list_messages(
        self,
        session_id: int,
        *,
        after: int = 0,
        limit: int = 100,
    ) -> object:
        await self.get_session(session_id)
        return await self._repository.get_messages_after(
            session_id,
            after=after,
            limit=limit,
        )

    async def stream_events(
        self,
        session_id: int,
        *,
        after: int = 0,
        poll_interval_seconds: float = 0.5,
    ) -> AsyncIterator[dict[str, Any]]:
        await self.get_session(session_id)
        cursor = after
        async with self._broadcast.subscribe(session_id) as queue:
            while True:
                messages = await self._repository.get_messages_after(
                    session_id,
                    after=cursor,
                )
                for message in messages:
                    cursor = max(cursor, int(message.sequence))
                    yield {
                        "type": "message",
                        **message_to_dict(message),
                    }
                if messages:
                    continue

                current_session = await self._repository.get_session(session_id)
                if (
                    current_session is None
                    or current_session.status in TERMINAL_SESSION_STATUSES
                ):
                    if current_session is not None:
                        yield {
                            "type": current_session.status,
                            "session_id": session_id,
                        }
                    return

                try:
                    live_event = await asyncio.wait_for(
                        queue.get(),
                        timeout=poll_interval_seconds,
                    )
                except TimeoutError:
                    continue
                sequence = message_event_sequence(live_event)
                if sequence is not None:
                    cursor = max(cursor, sequence)
                yield live_event


def flatten_message_event(event: dict[str, object]) -> dict[str, object]:
    message = event.get("message")
    if event.get("type") == "message" and isinstance(message, dict):
        return {"type": "message", **message}
    return event


def message_event_sequence(event: dict[str, object]) -> int | None:
    flattened = flatten_message_event(event)
    if flattened.get("type") != "message":
        return None
    sequence = flattened.get("sequence")
    return sequence if isinstance(sequence, int) else None


def message_to_dict(message: object) -> dict[str, object]:
    return {
        "id": str(message.id),
        "session_id": message.session_id,
        "sequence": message.sequence,
        "role": message.role,
        "content": message.content,
        "additional_kwargs": dict(message.additional_kwargs or {}),
        "created_at": (
            message.created_at.isoformat()
            if hasattr(message.created_at, "isoformat")
            else message.created_at
        ),
    }

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    SessionBroadcastDep,
    SessionRepositoryDep,
)
from app.schemas.sessions import SessionDetail, SessionMessage

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
SSE_POLL_INTERVAL_SECONDS = 0.5
TERMINAL_SESSION_STATUSES = {"completed", "failed", "interrupted"}


@router.get("/{session_id}")
async def get_session(
    session_id: int,
    repository: SessionRepositoryDep,
) -> SessionDetail:
    runtime_session = await repository.get_session(session_id)
    if runtime_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_session_detail(runtime_session)


@router.get("/{session_id}/messages")
async def list_session_messages(
    session_id: int,
    repository: SessionRepositoryDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SessionMessage]:
    runtime_session = await repository.get_session(session_id)
    if runtime_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    messages = await repository.get_messages_after(session_id, after=after, limit=limit)
    return [SessionMessage.model_validate(m) for m in messages]


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: int,
    repository: SessionRepositoryDep,
    broadcast: SessionBroadcastDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    runtime_session = await repository.get_session(session_id)
    if runtime_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async def event_stream():
        cursor = after
        async with broadcast.subscribe(session_id) as queue:
            while True:
                messages = await repository.get_messages_after(session_id, after=cursor)
                for message in messages:
                    cursor = max(cursor, int(message.sequence))
                    event = {
                        "type": "message",
                        "message": _message_to_dict(message),
                    }
                    yield format_session_sse(event)
                if messages:
                    continue

                current_session = await repository.get_session(session_id)
                if (
                    current_session is None
                    or current_session.status in TERMINAL_SESSION_STATUSES
                ):
                    return

                try:
                    live_event = await asyncio.wait_for(
                        queue.get(), timeout=SSE_POLL_INTERVAL_SECONDS
                    )
                except TimeoutError:
                    continue
                if live_event.get("type") == "message":
                    message_payload = live_event.get("message")
                    if isinstance(message_payload, dict):
                        sequence = message_payload.get("sequence")
                        if isinstance(sequence, int):
                            cursor = max(cursor, sequence)
                yield format_session_sse(live_event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def format_session_sse(event: dict[str, object]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    if event.get("type") == "message":
        message = event.get("message")
        if isinstance(message, dict) and isinstance(message.get("sequence"), int):
            return f"id: {message['sequence']}\nevent: message\ndata: {data}\n\n"
    return f"event: {event.get('type', 'live')}\ndata: {data}\n\n"


def _to_session_detail(runtime_session) -> SessionDetail:
    return SessionDetail(
        id=runtime_session.id,
        thread_id=runtime_session.thread_id,
        status=runtime_session.status,
        title=runtime_session.title,
        latest_sequence=getattr(runtime_session, "latest_sequence", 0) or 0,
        created_at=runtime_session.created_at,
        updated_at=runtime_session.updated_at,
    )


def _message_to_dict(message) -> dict[str, object]:
    return {
        "id": str(message.id),
        "session_id": message.session_id,
        "sequence": message.sequence,
        "role": message.role,
        "content": message.content,
        "additional_kwargs": dict(message.additional_kwargs or {}),
        "created_at": message.created_at.isoformat()
        if hasattr(message.created_at, "isoformat")
        else message.created_at,
    }

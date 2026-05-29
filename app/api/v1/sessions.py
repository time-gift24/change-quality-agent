import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    SessionServiceDep,
)
from app.schemas.sessions import SessionDetail, SessionMessage
from app.services.sessions import (
    SessionNotFoundError,
    flatten_message_event,
    message_event_sequence,
    message_to_dict,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
SSE_POLL_INTERVAL_SECONDS = 0.5


@router.get("/{session_id}")
async def get_session(
    session_id: int,
    service: SessionServiceDep,
) -> SessionDetail:
    try:
        runtime_session = await service.get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return _to_session_detail(runtime_session)


@router.get("/{session_id}/messages")
async def list_session_messages(
    session_id: int,
    service: SessionServiceDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SessionMessage]:
    try:
        messages = await service.list_messages(session_id, after=after, limit=limit)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return [SessionMessage.model_validate(m) for m in messages]


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: int,
    service: SessionServiceDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    try:
        await service.get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    async def event_stream():
        async for event in service.stream_events(
            session_id,
            after=after,
            poll_interval_seconds=SSE_POLL_INTERVAL_SECONDS,
        ):
            yield format_session_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def format_session_sse(event: dict[str, object]) -> str:
    event = flatten_message_event(event)
    data = json.dumps(event, ensure_ascii=False, default=str)
    if event.get("type") == "message":
        sequence = event.get("sequence")
        if isinstance(sequence, int):
            return f"id: {sequence}\nevent: message\ndata: {data}\n\n"
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


_message_to_dict = message_to_dict

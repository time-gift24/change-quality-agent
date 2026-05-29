import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import (
    SopQualityServiceDep,
)
from app.schemas.sop_quality_checks import (
    SopQualityCheckDetail,
    SopQualityCheckEvent,
    SopQualityCheckStartResponse,
    SopQualityCheckSummary,
)
from app.services.sop_quality import SopQualityCheckNotFoundError, message_to_event

router = APIRouter(prefix="/api/sop-quality-checks", tags=["sop-quality-checks"])
SSE_POLL_INTERVAL_SECONDS = 0.5


@router.post("")
async def start_sop_quality_check(
    service: SopQualityServiceDep,
    sop_id: Annotated[str, Query(min_length=1)],
    env: Annotated[str, Query(min_length=1)],
) -> JSONResponse:
    result = await service.start_check(sop_id, env)

    status_code = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
    return JSONResponse(
        status_code=status_code,
        content=SopQualityCheckStartResponse(**result.__dict__).model_dump(mode="json"),
    )


@router.get("")
async def list_sop_quality_checks(
    service: SopQualityServiceDep,
    sop_id: Annotated[str | None, Query(min_length=1)] = None,
    env: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SopQualityCheckSummary]:
    return await service.list_checks(sop_id=sop_id, env_key=env, limit=limit)


@router.get("/{check_id}")
async def get_sop_quality_check(
    check_id: UUID,
    service: SopQualityServiceDep,
) -> SopQualityCheckDetail:
    try:
        return await service.get_check_detail(check_id)
    except SopQualityCheckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.get("/{check_id}/events")
async def get_sop_quality_check_events(
    check_id: UUID,
    service: SopQualityServiceDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> list[SopQualityCheckEvent]:
    try:
        return await service.get_events(check_id, after=after)
    except SopQualityCheckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.get("/{check_id}/stream")
async def stream_sop_quality_check(
    check_id: UUID,
    service: SopQualityServiceDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    try:
        await service.ensure_check_exists(check_id)
    except SopQualityCheckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    async def event_stream():
        async for event in service.stream_events(
            check_id,
            after=after,
            poll_interval_seconds=SSE_POLL_INTERVAL_SECONDS,
        ):
            yield format_sse_event(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def format_sse_event(event: dict[str, object]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    event_type = event.get("type", "live")
    sequence = event.get("sequence")
    if isinstance(sequence, int):
        return f"id: {sequence}\nevent: {event_type}\ndata: {data}\n\n"
    return f"event: {event_type}\ndata: {data}\n\n"


def format_sse(event: dict[str, object]) -> str:
    return format_sse_event(event)


def format_live_sse(event: dict[str, object]) -> str:
    return format_sse_event(event)


def format_message_sse(message, check_id: UUID) -> str:
    return format_sse_event(message_to_event(message, check_id))

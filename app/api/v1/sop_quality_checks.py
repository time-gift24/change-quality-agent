import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent.sop_quality.display import display_state_from_graph_values
from app.api.deps import SessionDep, SopQualityCheckRepositoryDep
from app.core.config import settings
from app.schemas.sop_quality_checks import (
    SopQualityCheckDetail,
    SopQualityCheckEvent,
    SopQualityCheckStartResponse,
    SopQualityCheckStatus,
    SopQualityCheckSummary,
)
from app.services.sop_quality import SopQualityService
from app.services.sop_quality_runner import run_sop_quality_check_with_new_session
from app.services.sop_quality_streaming import SopQualityBroadcast

router = APIRouter(prefix="/api/sop-quality-checks", tags=["sop-quality-checks"])
SSE_POLL_INTERVAL_SECONDS = 0.5
TERMINAL_CHECK_STATUSES = {"succeeded", "failed", "cancelled", "interrupted"}
TERMINAL_EVENT_TYPES = {"completed", "failed", "cancelled", "interrupted"}
_broadcast = SopQualityBroadcast()


@router.post("")
async def start_sop_quality_check(
    background_tasks: BackgroundTasks,
    request: Request,
    session: SessionDep,
    repository: SopQualityCheckRepositoryDep,
    sop_id: Annotated[str, Query(min_length=1)],
    env: Annotated[str, Query(min_length=1)],
) -> JSONResponse:
    def schedule_check(check_id: UUID) -> None:
        executor = getattr(request.app.state, "sop_quality_check_executor", None)
        if executor is not None:
            background_tasks.add_task(executor, check_id)
            return
        background_tasks.add_task(
            run_sop_quality_check_with_new_session,
            check_id,
            broadcast=_broadcast,
        )

    service = SopQualityService(
        settings=settings,
        repository=repository,
        schedule_check=schedule_check,
        commit=session.commit,
    )
    result = await service.start_check(sop_id, env)

    status_code = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
    return JSONResponse(
        status_code=status_code,
        content=SopQualityCheckStartResponse(**result.__dict__).model_dump(mode="json"),
    )


@router.get("")
async def list_sop_quality_checks(
    repository: SopQualityCheckRepositoryDep,
    sop_id: Annotated[str | None, Query(min_length=1)] = None,
    env: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SopQualityCheckSummary]:
    checks = await repository.list_checks(sop_id=sop_id, env_key=env, limit=limit)
    return [_check_to_summary(check) for check in checks]


@router.get("/{check_id}")
async def get_sop_quality_check(
    check_id: UUID,
    repository: SopQualityCheckRepositoryDep,
) -> SopQualityCheckDetail:
    check = await repository.get_check(check_id)
    if check is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _check_to_detail(check)


@router.get("/{check_id}/events")
async def get_sop_quality_check_events(
    check_id: UUID,
    repository: SopQualityCheckRepositoryDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> list[SopQualityCheckEvent]:
    check = await repository.get_check(check_id)
    if check is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    events = await repository.get_events_after(check_id, after=after)
    return [SopQualityCheckEvent(**event_to_dict(event)) for event in events]


@router.get("/{check_id}/stream")
async def stream_sop_quality_check(
    check_id: UUID,
    repository: SopQualityCheckRepositoryDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    check = await repository.get_check(check_id)
    if check is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async def event_stream():
        cursor = after
        async with _broadcast.subscribe(check_id) as queue:
            while True:
                events = await repository.get_events_after(check_id, after=cursor)
                for event in events:
                    cursor = max(cursor, int(event.sequence))
                    event_dict = event_to_dict(event)
                    yield format_sse(event_dict)
                    if event.type in TERMINAL_EVENT_TYPES:
                        return
                if events:
                    continue

                current_check = await repository.get_check(check_id)
                if current_check is None or current_check.status in TERMINAL_CHECK_STATUSES:
                    return
                try:
                    live_event = await asyncio.wait_for(
                        queue.get(),
                        timeout=SSE_POLL_INTERVAL_SECONDS,
                    )
                except TimeoutError:
                    continue
                sequence = live_event.get("sequence")
                if isinstance(sequence, int):
                    cursor = max(cursor, sequence)
                yield format_live_sse(live_event)
                if live_event.get("type") in TERMINAL_EVENT_TYPES:
                    return

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def format_sse(event: dict[str, object]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    return f"id: {event['sequence']}\nevent: {event['type']}\ndata: {data}\n\n"


def format_live_sse(event: dict[str, object]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    event_type = event.get("type", "live")
    sequence = event.get("sequence")
    if isinstance(sequence, int):
        return f"id: {sequence}\nevent: {event_type}\ndata: {data}\n\n"
    return f"event: {event_type}\ndata: {data}\n\n"


def event_to_dict(event) -> dict[str, object]:
    return {
        "check_id": event.check_id,
        "sequence": event.sequence,
        "type": event.type,
        "node": getattr(event, "node", None),
        "checkpoint_id": getattr(event, "checkpoint_id", None),
        "task_id": getattr(event, "task_id", None),
        "message": getattr(event, "message", None),
        "created_at": event.created_at,
    }


def _check_to_summary(check) -> SopQualityCheckSummary:
    return SopQualityCheckSummary(
        check_id=check.id,
        sop_id=check.sop_id,
        env_key=check.env_key,
        status=SopQualityCheckStatus(check.status),
        quality_result=check.quality_result,
        latest_sequence=_latest_sequence(check),
        created_at=check.created_at,
        started_at=check.started_at,
        finished_at=check.finished_at,
        error_summary=_error_summary(check.error),
    )


def _check_to_detail(check) -> SopQualityCheckDetail:
    summary = _check_to_summary(check)
    values = _graph_values_from_check(check)
    display_state = display_state_from_graph_values(
        values,
        latest_sequence=summary.latest_sequence,
        is_running=check.status in {"pending", "running"},
    )
    return SopQualityCheckDetail(
        **summary.model_dump(),
        graph_name=check.graph_name,
        graph_version=check.graph_version,
        thread_id=check.thread_id,
        checkpoint_ns=check.checkpoint_ns,
        current_checkpoint_id=check.current_checkpoint_id,
        result=check.result,
        error=check.error,
        display_state=display_state,
    )


def _graph_values_from_check(check) -> dict[str, object]:
    values: dict[str, object] = {"sop_snapshot": getattr(check, "sop_snapshot", {})}
    if isinstance(check.result, dict):
        values["result"] = check.result
        if isinstance(check.result.get("findings"), list):
            values["findings"] = check.result["findings"]
        if isinstance(check.result.get("quality_result"), str):
            values["quality_result"] = check.result["quality_result"]
        if isinstance(check.result.get("review_output"), str):
            values["review_output"] = check.result["review_output"]
        if isinstance(check.result.get("submission_result"), dict):
            values["submission_result"] = check.result["submission_result"]
    return values


def _latest_sequence(check) -> int:
    explicit_sequence = getattr(check, "latest_sequence", None)
    if isinstance(explicit_sequence, int):
        return explicit_sequence
    events = getattr(check, "__dict__", {}).get("events", [])
    if not events:
        return 0
    return max(int(event.sequence) for event in events)


def _error_summary(error: object) -> str | None:
    if isinstance(error, dict):
        message = error.get("message")
        return message if isinstance(message, str) else None
    return None

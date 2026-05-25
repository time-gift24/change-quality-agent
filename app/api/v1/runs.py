import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import RunRepositoryDep
from app.api.v1.run_views import run_to_summary
from app.schemas.runs import RunDebug, RunDetail, RunStatus

router = APIRouter(prefix="/api/runs", tags=["runs"])

SSE_POLL_INTERVAL_SECONDS = 0.5
TERMINAL_EVENT_TYPES = {"done", "error"}
TERMINAL_RUN_STATUSES = {
    RunStatus.success.value,
    RunStatus.error.value,
    RunStatus.timeout.value,
    RunStatus.interrupted.value,
}


@router.get("/{run_id}")
async def get_run(
    run_id: UUID,
    repository: RunRepositoryDep,
    debug: Annotated[bool, Query()] = False,
) -> RunDetail:
    run = await repository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    summary = run_to_summary(run)
    run_debug = _build_debug(run) if debug else None
    return RunDetail(**summary.model_dump(), debug=run_debug)


@router.get("/{run_id}/events")
async def get_run_events(
    run_id: UUID,
    repository: RunRepositoryDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    run = await repository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async def event_stream():
        # v1 polls durable events. An in-process broadcast can be added later
        # for lower latency without changing the public SSE envelope.
        cursor = after
        while True:
            events = await repository.get_events_after(run_id, after=cursor)
            for event in events:
                cursor = max(cursor, int(event.sequence))
                yield format_sse(event_to_dict(event))
                if event.type in TERMINAL_EVENT_TYPES:
                    return
            if events:
                continue

            current_run = await repository.get_run(run_id)
            if current_run is None or current_run.status in TERMINAL_RUN_STATUSES:
                return
            await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def format_sse(event: dict[str, object]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    return f"id: {event['sequence']}\nevent: {event['type']}\ndata: {data}\n\n"


def event_to_dict(event) -> dict[str, object]:
    return {
        "run_id": event.run_id,
        "sequence": event.sequence,
        "type": event.type,
        "node": event.node,
        "thread_id": event.thread_id,
        "checkpoint_id": event.checkpoint_id,
        "task_id": event.task_id,
        "payload": event.payload,
        "created_at": event.created_at,
    }


def _build_debug(run) -> RunDebug:
    return RunDebug(
        thread_id=run.thread_id,
        current_checkpoint_id=run.current_checkpoint_id,
        raw_graph_output=run.raw_graph_output,
        raw_last_event=_raw_last_event(run),
    )


def _raw_last_event(run) -> dict[str, object] | None:
    events = getattr(run, "__dict__", {}).get("events", [])
    if not events:
        return None
    latest_event = max(events, key=lambda event: event.sequence)
    return event_to_dict(latest_event)

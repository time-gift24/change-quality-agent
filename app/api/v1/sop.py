from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import RunRepositoryDep, SessionDep, SopClientDep
from app.api.v1.run_views import run_to_summary
from app.core.config import settings
from app.schemas.runs import ActiveRunConflict, RunStartResponse, RunSummary
from app.schemas.sop import EnvironmentPublic, SopSnapshot
from app.services.sop_client import SopClientError, SopNotFoundError
from app.services.sop_quality import (
    SopQualityService,
    run_sop_quality_graph_with_new_session,
)

router = APIRouter(prefix="/api/sop", tags=["sop"])


@router.get("/environments")
async def list_environments() -> list[EnvironmentPublic]:
    return [
        EnvironmentPublic(**environment.public_dict())
        for environment in settings.environments
    ]


@router.get("/{sop_id}")
async def get_sop_preview(
    sop_id: str,
    sop_client: SopClientDep,
    env: Annotated[str, Query()],
) -> SopSnapshot:
    _get_environment_or_404(env)
    try:
        return await sop_client.get_sop(sop_id, env)
    except SopNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except SopClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY) from exc


@router.post("/{sop_id}/runs")
async def start_sop_run(
    sop_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    session: SessionDep,
    sop_client: SopClientDep,
    repository: RunRepositoryDep,
    env: Annotated[str, Query()],
) -> RunStartResponse:
    _get_environment_or_404(env)

    def schedule_run(run_id):
        executor = getattr(
            request.app.state,
            "sop_run_executor",
            run_sop_quality_graph_with_new_session,
        )
        background_tasks.add_task(executor, run_id)

    service = SopQualityService(
        settings=settings,
        sop_client=sop_client,
        repository=repository,
        schedule_run=schedule_run,
        commit=session.commit,
    )
    try:
        result = await service.start_run(sop_id, env)
    except SopNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except SopClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY) from exc

    if not result.accepted and result.active_run_id is not None:
        conflict = ActiveRunConflict(
            message=result.message or "An active run already exists.",
            active_run_id=result.active_run_id,
            status_url=result.status_url,
            events_url=result.events_url,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict.model_dump(mode="json"),
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=RunStartResponse(
            run_id=result.run_id,
            status=result.status,
            status_url=result.status_url,
            events_url=result.events_url,
        ).model_dump(mode="json"),
    )


@router.get("/recent/runs")
async def list_recent_sop_runs(
    repository: RunRepositoryDep,
    env: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RunSummary]:
    _get_environment_or_404(env)
    runs = await repository.list_recent_sop_runs(env_key=env, limit=limit)
    return [run_to_summary(run) for run in runs]


@router.get("/{sop_id}/runs")
async def list_sop_runs(
    sop_id: str,
    repository: RunRepositoryDep,
    env: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RunSummary]:
    _get_environment_or_404(env)
    runs = await repository.list_sop_runs(sop_id=sop_id, env_key=env, limit=limit)
    return [run_to_summary(run) for run in runs]


def _get_environment_or_404(env_key: str):
    try:
        return settings.get_environment(env_key)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

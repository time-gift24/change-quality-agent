from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse

from app.api.deps import AgentRepositoryDep, RunRepositoryDep, SessionDep
from app.repositories.agents import (
    AgentDisabledError,
    AgentRepository,
    AgentDraftInvalidError,
    AgentKeyExistsError,
    AgentNotFoundError,
    AgentVersionNotFoundError,
)
from app.schemas.agents import (
    AgentCreate,
    AgentDetail,
    AgentDraftConfig,
    AgentDraftUpdate,
    AgentSummary,
    AgentTestRunCreate,
    AgentVersionDetail,
    AgentVersionSummary,
)
from app.schemas.runs import RunStartResponse
from app.services.agents import AgentService, run_agent_test_with_new_session

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        agent = await service.create_agent(request)
    except AgentKeyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT) from exc
    return agent_to_detail(agent)


@router.get("")
async def list_agents(
    repository: AgentRepositoryDep,
    include_deleted: Annotated[bool, Query()] = False,
) -> list[AgentSummary]:
    agents = await repository.list_agents(include_deleted=include_deleted)
    return [agent_to_summary(agent) for agent in agents]


@router.get("/{agent_key}")
async def get_agent(
    agent_key: str,
    repository: AgentRepositoryDep,
) -> AgentDetail:
    agent = await repository.get_agent(agent_key)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return agent_to_detail(agent)


@router.patch("/{agent_key}/draft")
async def update_agent_draft(
    agent_key: str,
    request: AgentDraftUpdate,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        agent = await service.update_draft(agent_key, request)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return agent_to_detail(agent)


@router.post("/{agent_key}/publish", status_code=status.HTTP_201_CREATED)
async def publish_agent(
    agent_key: str,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentVersionDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        version = await service.publish_agent(agent_key)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except AgentDraftInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc
    return version_to_detail(version)


@router.post("/{agent_key}/test-runs")
async def start_agent_test_run(
    agent_key: str,
    payload: AgentTestRunCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: SessionDep,
    repository: AgentRepositoryDep,
    run_repository: RunRepositoryDep,
) -> RunStartResponse:
    def schedule_run(run_id):
        executor = getattr(
            request.app.state,
            "agent_test_run_executor",
            run_agent_test_with_new_session,
        )
        background_tasks.add_task(executor, run_id)

    service = AgentService(
        repository=repository,
        run_repository=run_repository,
        schedule_test_run=schedule_run,
        commit=session.commit,
    )
    try:
        current_user = getattr(request.state, "current_user", None)
        result = await service.start_test_run(
            agent_key,
            payload,
            current_user=current_user,
        )
    except AgentDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except AgentVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=RunStartResponse(
            run_id=result.run_id,
            status=result.status,
            status_url=result.status_url,
            events_url=result.events_url,
        ).model_dump(mode="json"),
    )


@router.get("/{agent_key}/versions")
async def list_agent_versions(
    agent_key: str,
    repository: AgentRepositoryDep,
) -> list[AgentVersionSummary]:
    try:
        await _require_agent(repository, agent_key)
        versions = await repository.list_versions(agent_key)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return [version_to_summary(version) for version in versions]


@router.get("/{agent_key}/versions/{version_number}")
async def get_agent_version(
    agent_key: str,
    version_number: Annotated[int, Path(ge=1)],
    repository: AgentRepositoryDep,
) -> AgentVersionDetail:
    try:
        await _require_agent(repository, agent_key)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    version = await repository.get_version_by_number(agent_key, version_number)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return version_to_detail(version)


@router.delete("/{agent_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_key: str,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> Response:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        await service.delete_agent(agent_key)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def agent_to_summary(agent) -> AgentSummary:
    draft = _draft_config_or_none(agent)
    return AgentSummary(
        id=agent.id,
        key=agent.key,
        display_name=agent.display_name,
        description=agent.description,
        enabled=agent.enabled,
        has_draft=draft is not None,
        latest_version=version_to_summary(agent.latest_version)
        if agent.latest_version is not None
        else None,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def agent_to_detail(agent) -> AgentDetail:
    summary = agent_to_summary(agent)
    return AgentDetail(
        id=summary.id,
        key=summary.key,
        display_name=summary.display_name,
        description=summary.description,
        enabled=summary.enabled,
        has_draft=summary.has_draft,
        latest_version=summary.latest_version,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        draft=_draft_config_or_none(agent),
    )


def version_to_summary(version) -> AgentVersionSummary:
    return AgentVersionSummary.model_validate(version)


def version_to_detail(version) -> AgentVersionDetail:
    return AgentVersionDetail.model_validate(version)


async def _require_agent(repository: AgentRepository, agent_key: str):
    agent = await repository.get_agent(agent_key)
    if agent is None:
        raise AgentNotFoundError(agent_key)
    return agent


def _draft_config_or_none(agent) -> AgentDraftConfig | None:
    draft_config = agent.draft_config
    if draft_config is None:
        return None
    return AgentDraftConfig.model_validate(draft_config)

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)

from app.api.deps import AgentRepositoryDep, SessionDep
from app.repositories.agents import (
    AgentRepository,
    AgentDraftInvalidError,
    AgentNotFoundError,
)
from app.schemas.agents import (
    AgentCreate,
    AgentDetail,
    AgentDraftConfig,
    AgentDraftUpdate,
    AgentSummary,
    AgentVersionDetail,
    AgentVersionSummary,
)
from app.services.agents import AgentService

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentDetail:
    service = AgentService(repository=repository, commit=session.commit)
    agent = await service.create_agent(request)
    return agent_to_detail(agent)


@router.get("")
async def list_agents(
    repository: AgentRepositoryDep,
    include_deleted: Annotated[bool, Query()] = False,
) -> list[AgentSummary]:
    agents = await repository.list_agents(include_deleted=include_deleted)
    return [agent_to_summary(agent) for agent in agents]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: Annotated[UUID, Path()],
    repository: AgentRepositoryDep,
) -> AgentDetail:
    agent = await repository.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return agent_to_detail(agent)


@router.patch("/{agent_id}/draft")
async def update_agent_draft(
    agent_id: Annotated[UUID, Path()],
    request: AgentDraftUpdate,
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        agent = await service.update_draft(agent_id, request)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return agent_to_detail(agent)


@router.post("/{agent_id}/publish", status_code=status.HTTP_201_CREATED)
async def publish_agent(
    agent_id: Annotated[UUID, Path()],
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> AgentVersionDetail:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        version = await service.publish_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except AgentDraftInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc
    return version_to_detail(version)


@router.get("/{agent_id}/versions")
async def list_agent_versions(
    agent_id: Annotated[UUID, Path()],
    repository: AgentRepositoryDep,
) -> list[AgentVersionSummary]:
    try:
        await _require_agent(repository, agent_id)
        versions = await repository.list_versions(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return [version_to_summary(version) for version in versions]


@router.get("/{agent_id}/versions/{version_number}")
async def get_agent_version(
    agent_id: Annotated[UUID, Path()],
    version_number: Annotated[int, Path(ge=1)],
    repository: AgentRepositoryDep,
) -> AgentVersionDetail:
    try:
        await _require_agent(repository, agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    version = await repository.get_version_by_number(agent_id, version_number)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return version_to_detail(version)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: Annotated[UUID, Path()],
    session: SessionDep,
    repository: AgentRepositoryDep,
) -> Response:
    service = AgentService(repository=repository, commit=session.commit)
    try:
        await service.delete_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def agent_to_summary(agent) -> AgentSummary:
    draft = _draft_config_or_none(agent)
    return AgentSummary(
        id=agent.id,
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


async def _require_agent(repository: AgentRepository, agent_id: UUID):
    agent = await repository.get_agent(agent_id)
    if agent is None:
        raise AgentNotFoundError(agent_id)
    return agent


def _draft_config_or_none(agent) -> AgentDraftConfig | None:
    draft_config = agent.draft_config
    if draft_config is None:
        return None
    return AgentDraftConfig.model_validate(draft_config)

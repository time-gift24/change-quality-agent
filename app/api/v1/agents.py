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

from app.api.deps import AgentServiceDep
from app.schemas.agents import (
    AgentCreate,
    AgentDetail,
    AgentDraftConfig,
    AgentDraftUpdate,
    AgentSummary,
    AgentVersionDetail,
    AgentVersionSummary,
)
from app.services.agents import (
    AgentDraftInvalidError,
    AgentNotFoundError,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    service: AgentServiceDep,
) -> AgentDetail:
    agent = await service.create_agent(request)
    return agent_to_detail(agent)


@router.get("")
async def list_agents(
    service: AgentServiceDep,
    include_deleted: Annotated[bool, Query()] = False,
) -> list[AgentSummary]:
    agents = await service.list_agents(include_deleted=include_deleted)
    return [agent_to_summary(agent) for agent in agents]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: Annotated[UUID, Path()],
    service: AgentServiceDep,
) -> AgentDetail:
    try:
        agent = await service.get_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return agent_to_detail(agent)


@router.patch("/{agent_id}/draft")
async def update_agent_draft(
    agent_id: Annotated[UUID, Path()],
    request: AgentDraftUpdate,
    service: AgentServiceDep,
) -> AgentDetail:
    try:
        agent = await service.update_draft(agent_id, request)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return agent_to_detail(agent)


@router.post("/{agent_id}/publish", status_code=status.HTTP_201_CREATED)
async def publish_agent(
    agent_id: Annotated[UUID, Path()],
    service: AgentServiceDep,
) -> AgentVersionDetail:
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
    service: AgentServiceDep,
) -> list[AgentVersionSummary]:
    try:
        versions = await service.list_versions(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return [version_to_summary(version) for version in versions]


@router.get("/{agent_id}/versions/{version_number}")
async def get_agent_version(
    agent_id: Annotated[UUID, Path()],
    version_number: Annotated[int, Path(ge=1)],
    service: AgentServiceDep,
) -> AgentVersionDetail:
    try:
        version = await service.get_version(agent_id, version_number)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    return version_to_detail(version)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: Annotated[UUID, Path()],
    service: AgentServiceDep,
) -> Response:
    try:
        await service.delete_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def agent_to_summary(agent: object) -> AgentSummary:
    draft = _draft_config_or_none(agent)
    return AgentSummary(
        id=agent.id,
        display_name=agent.display_name,
        description=agent.description,
        enabled=agent.enabled,
        has_draft=draft is not None,
        latest_version=(
            version_to_summary(agent.latest_version)
            if agent.latest_version is not None
            else None
        ),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def agent_to_detail(agent: object) -> AgentDetail:
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


def version_to_summary(version: object) -> AgentVersionSummary:
    return AgentVersionSummary.model_validate(version)


def version_to_detail(version: object) -> AgentVersionDetail:
    return AgentVersionDetail.model_validate(version)


def _draft_config_or_none(agent: object) -> AgentDraftConfig | None:
    draft_config = agent.draft_config
    if draft_config is None:
        return None
    return AgentDraftConfig.model_validate(draft_config)

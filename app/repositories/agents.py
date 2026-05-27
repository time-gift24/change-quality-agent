from datetime import UTC, datetime
from typing import Any, Final, Mapping
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agents import Agent, AgentVersion
from app.schemas.agents import AgentDraftConfig


class _UnsetType:
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _UnsetType()


class AgentKeyExistsError(Exception):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


class AgentNotFoundError(Exception):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


class AgentDisabledError(Exception):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


class AgentDraftInvalidError(Exception):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


class AgentVersionNotFoundError(Exception):
    def __init__(self, version_id: UUID) -> None:
        self.version_id = version_id
        super().__init__(str(version_id))


def validate_draft_config(
    key: str,
    draft: AgentDraftConfig | Mapping[str, Any] | None,
) -> AgentDraftConfig:
    try:
        return (
            draft
            if isinstance(draft, AgentDraftConfig)
            else AgentDraftConfig.model_validate(draft)
        )
    except ValidationError as exc:
        raise AgentDraftInvalidError(key) from exc


def dump_draft_config(
    key: str,
    draft: AgentDraftConfig | Mapping[str, Any],
) -> dict[str, Any]:
    return validate_draft_config(key, draft).model_dump(mode="json", by_alias=True)


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_agent(
        self,
        *,
        key: str,
        display_name: str,
        description: str | None,
        draft: AgentDraftConfig | Mapping[str, Any],
        created_by: str | None = None,
    ) -> Agent:
        agent = Agent(
            key=key,
            display_name=display_name,
            description=description,
            draft_config=dump_draft_config(key, draft),
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(agent)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise AgentKeyExistsError(key) from exc
        return agent

    async def list_agents(self, *, include_deleted: bool = False) -> list[Agent]:
        statement = (
            select(Agent)
            .options(selectinload(Agent.latest_version))
            .order_by(Agent.created_at.desc(), Agent.key)
        )
        if not include_deleted:
            statement = statement.where(Agent.deleted_at.is_(None))
        return list((await self._session.scalars(statement)).all())

    async def get_agent(
        self,
        key: str,
        *,
        include_deleted: bool = False,
    ) -> Agent | None:
        statement = (
            select(Agent)
            .options(selectinload(Agent.latest_version))
            .where(Agent.key == key)
            .limit(1)
        )
        if not include_deleted:
            statement = statement.where(Agent.deleted_at.is_(None))
        return await self._session.scalar(statement)

    async def update_draft(
        self,
        key: str,
        *,
        display_name: str | _UnsetType = UNSET,
        description: str | None | _UnsetType = UNSET,
        enabled: bool | _UnsetType = UNSET,
        draft: AgentDraftConfig | Mapping[str, Any] | _UnsetType = UNSET,
        updated_by: str | None = None,
    ) -> Agent:
        """Update only fields whose arguments are not the public UNSET sentinel."""

        agent = await self._require_agent(key)
        if display_name is not UNSET:
            agent.display_name = display_name
        if description is not UNSET:
            agent.description = description
        if enabled is not UNSET:
            agent.enabled = enabled
        if draft is not UNSET:
            agent.draft_config = dump_draft_config(key, draft)
        if updated_by is not None:
            agent.updated_by = updated_by
        await self._session.flush()
        return await self._require_agent(key)

    async def publish_agent(
        self,
        key: str,
        *,
        published_by: str | None = None,
    ) -> AgentVersion:
        agent = await self._require_agent(key, lock=True)
        draft = validate_draft_config(key, agent.draft_config)
        version = AgentVersion(
            agent_id=agent.id,
            version_number=await self._next_version_number(agent.id),
            system_prompt=draft.system_prompt,
            model=draft.model,
            provider_key=draft.provider_key,
            model_config=dict(draft.model_parameters),
            tool_allowlist=list(draft.tool_allowlist),
            mcp_server_ids=list(draft.mcp_server_ids),
            published_by=published_by,
        )
        self._session.add(version)
        await self._session.flush()
        agent.latest_version_id = version.id
        if published_by is not None:
            agent.updated_by = published_by
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def list_versions(self, key: str) -> list[AgentVersion]:
        statement = (
            select(AgentVersion)
            .join(Agent, AgentVersion.agent_id == Agent.id)
            .where(Agent.key == key)
            .order_by(AgentVersion.version_number.desc())
        )
        return list((await self._session.scalars(statement)).all())

    async def get_version_by_number(
        self,
        key: str,
        version_number: int,
    ) -> AgentVersion | None:
        statement = (
            select(AgentVersion)
            .join(Agent, AgentVersion.agent_id == Agent.id)
            .where(Agent.key == key)
            .where(AgentVersion.version_number == version_number)
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def get_version_by_id(self, version_id: UUID) -> AgentVersion | None:
        return await self._session.get(AgentVersion, version_id)

    async def soft_delete(
        self,
        key: str,
        *,
        updated_by: str | None = None,
    ) -> Agent:
        agent = await self._require_agent(key)
        agent.deleted_at = datetime.now(UTC)
        if updated_by is not None:
            agent.updated_by = updated_by
        await self._session.flush()
        return await self._require_agent(key, include_deleted=True)

    async def _require_agent(
        self,
        key: str,
        *,
        include_deleted: bool = False,
        lock: bool = False,
    ) -> Agent:
        statement = (
            select(Agent)
            .options(selectinload(Agent.latest_version))
            .where(Agent.key == key)
            .execution_options(populate_existing=True)
        )
        if not include_deleted:
            statement = statement.where(Agent.deleted_at.is_(None))
        if lock:
            statement = statement.with_for_update()
        agent = await self._session.scalar(statement)
        if agent is None:
            raise AgentNotFoundError(key)
        return agent

    async def _require_active_agent(
        self,
        key: str,
        *,
        lock: bool = False,
    ) -> Agent:
        return await self._require_agent(key, lock=lock)

    async def _next_version_number(self, agent_id: UUID) -> int:
        statement = (
            select(func.coalesce(func.max(AgentVersion.version_number), 0)).where(
                AgentVersion.agent_id == agent_id
            )
        )
        latest_version_number = await self._session.scalar(statement)
        return int(latest_version_number or 0) + 1

    def _dump_draft(
        self,
        key: str,
        draft: AgentDraftConfig | Mapping[str, Any],
    ) -> dict[str, Any]:
        return dump_draft_config(key, draft)

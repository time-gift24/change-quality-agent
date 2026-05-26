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

_UNSET: Final = object()


class AgentKeyExistsError(Exception):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


class AgentNotFoundError(Exception):
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
            draft_config=self._dump_draft(key, draft),
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
        display_name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        enabled: bool | object = _UNSET,
        draft: AgentDraftConfig | Mapping[str, Any] | object = _UNSET,
        updated_by: str | None = None,
    ) -> Agent:
        agent = await self._require_active_agent(key)
        if display_name is not _UNSET:
            agent.display_name = display_name  # type: ignore[assignment]
        if description is not _UNSET:
            agent.description = description  # type: ignore[assignment]
        if enabled is not _UNSET:
            agent.enabled = enabled  # type: ignore[assignment]
        if draft is not _UNSET:
            agent.draft_config = self._dump_draft(
                key,
                draft,  # type: ignore[arg-type]
            )
        if updated_by is not None:
            agent.updated_by = updated_by
        await self._session.flush()
        return agent

    async def publish_agent(
        self,
        key: str,
        *,
        published_by: str | None = None,
    ) -> AgentVersion:
        agent = await self._require_active_agent(key, lock=True)
        draft = self._validate_draft(key, agent.draft_config)
        version = AgentVersion(
            agent_id=agent.id,
            version_number=await self._next_version_number(agent.id),
            system_prompt=draft.system_prompt,
            model=draft.model,
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
        agent = await self._require_active_agent(key)
        agent.deleted_at = datetime.now(UTC)
        if updated_by is not None:
            agent.updated_by = updated_by
        await self._session.flush()
        return agent

    async def _require_active_agent(
        self,
        key: str,
        *,
        lock: bool = False,
    ) -> Agent:
        statement = (
            select(Agent).where(Agent.key == key).where(Agent.deleted_at.is_(None))
        )
        if lock:
            statement = statement.with_for_update()
        agent = await self._session.scalar(statement)
        if agent is None:
            raise AgentNotFoundError(key)
        return agent

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
        return self._validate_draft(key, draft).model_dump(mode="json", by_alias=True)

    def _validate_draft(
        self,
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

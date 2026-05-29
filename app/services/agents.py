import inspect
from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.core.llm_models import LlmProviderRuntimeConfig
from app.models.agents import Agent, AgentVersion
from app.repositories.agents import (
    AgentDraftInvalidError,
    AgentNotFoundError,
    AgentRepository,
)
from app.repositories.llm_providers import (
    LlmProviderNotFoundError,
    LlmProviderRepository,
)
from app.schemas.agents import AgentCreate, AgentDraftUpdate

Committer = Callable[[], object]


class DatabaseLlmProviderResolver:
    def __init__(self, repository: LlmProviderRepository) -> None:
        self._repository = repository

    async def resolve(self, provider_id: UUID) -> LlmProviderRuntimeConfig:
        provider = await self._repository.get_by_id(provider_id)
        if provider is None:
            raise LlmProviderNotFoundError(f"LLM provider not found: {provider_id}")
        if not provider.enabled:
            raise RuntimeError(f"LLM provider is disabled: {provider_id}")
        return LlmProviderRuntimeConfig(
            id=provider.id,
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            api_key=provider.api_key,
            default_headers=dict(provider.default_headers or {}),
            default_query=dict(provider.default_query or {}),
            enabled=provider.enabled,
        )


class AgentService:
    def __init__(
        self,
        repository: AgentRepository,
        commit: Committer | None = None,
    ) -> None:
        self._repository = repository
        self._commit = commit

    async def list_agents(self, *, include_deleted: bool = False) -> list[Agent]:
        return await self._repository.list_agents(include_deleted=include_deleted)

    async def get_agent(self, agent_id: UUID) -> Agent:
        return await self._require_agent(agent_id)

    async def create_agent(self, request: AgentCreate) -> Agent:
        agent = await self._repository.create_agent(
            display_name=request.display_name,
            description=request.description,
            draft=request.draft,
        )
        await self._commit_if_configured()
        return agent

    async def update_draft(
        self,
        agent_id: UUID,
        request: AgentDraftUpdate,
    ) -> Agent:
        agent = await self._repository.update_draft(
            agent_id,
            **self._draft_update_kwargs(request),
        )
        await self._commit_if_configured()
        return agent

    async def publish_agent(self, agent_id: UUID) -> AgentVersion:
        version = await self._repository.publish_agent(agent_id)
        await self._commit_if_configured()
        return version

    async def list_versions(self, agent_id: UUID) -> list[AgentVersion]:
        await self._require_agent(agent_id)
        return await self._repository.list_versions(agent_id)

    async def get_version(
        self,
        agent_id: UUID,
        version_number: int,
    ) -> AgentVersion:
        await self._require_agent(agent_id)
        version = await self._repository.get_version_by_number(
            agent_id,
            version_number,
        )
        if version is None:
            raise AgentNotFoundError(agent_id)
        return version

    async def delete_agent(self, agent_id: UUID) -> Agent:
        agent = await self._repository.soft_delete(agent_id)
        await self._commit_if_configured()
        return agent

    async def _require_agent(self, agent_id: UUID) -> Agent:
        agent = await self._repository.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        return agent

    def _draft_update_kwargs(self, request: AgentDraftUpdate) -> dict[str, Any]:
        fields_set = request.model_fields_set
        kwargs: dict[str, Any] = {}
        if "display_name" in fields_set and request.display_name is not None:
            kwargs["display_name"] = request.display_name
        if "description" in fields_set:
            kwargs["description"] = request.description
        if "enabled" in fields_set and request.enabled is not None:
            kwargs["enabled"] = request.enabled
        if "draft" in fields_set and request.draft is not None:
            kwargs["draft"] = request.draft
        return kwargs

    async def _commit_if_configured(self) -> None:
        if self._commit is None:
            return
        result = self._commit()
        if inspect.isawaitable(result):
            await result

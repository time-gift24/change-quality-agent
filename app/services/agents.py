import inspect
from collections.abc import Callable
from typing import Any

from app.models.agents import Agent, AgentVersion
from app.repositories.agents import AgentRepository
from app.schemas.agents import AgentCreate, AgentDraftUpdate

Committer = Callable[[], object]


class AgentService:
    def __init__(
        self,
        repository: AgentRepository,
        commit: Committer | None = None,
    ) -> None:
        self._repository = repository
        self._commit = commit

    async def create_agent(self, request: AgentCreate) -> Agent:
        agent = await self._repository.create_agent(
            key=request.key,
            display_name=request.display_name,
            description=request.description,
            draft=request.draft,
        )
        await self._commit_if_configured()
        return agent

    async def update_draft(
        self,
        agent_key: str,
        request: AgentDraftUpdate,
    ) -> Agent:
        agent = await self._repository.update_draft(
            agent_key,
            **self._draft_update_kwargs(request),
        )
        await self._commit_if_configured()
        return agent

    async def publish_agent(self, agent_key: str) -> AgentVersion:
        version = await self._repository.publish_agent(agent_key)
        await self._commit_if_configured()
        return version

    async def delete_agent(self, agent_key: str) -> Agent:
        agent = await self._repository.soft_delete(agent_key)
        await self._commit_if_configured()
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

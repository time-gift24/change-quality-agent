import inspect
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from app.core.llm_model_config import LlmModelParameters
from app.core.llm_models import LlmProviderRuntimeConfig
from app.models.agents import Agent, AgentVersion
from app.repositories.agents import (
    AgentDisabledError,
    AgentDraftInvalidError,
    AgentNotFoundError,
    AgentRepository,
    validate_draft_config,
)
from app.repositories.llm_providers import (
    LlmProviderNotFoundError,
    LlmProviderRepository,
)
from app.schemas.agents import (
    AgentCreate,
    AgentDraftConfig,
    AgentDraftUpdate,
    AgentSessionStart,
    AgentSessionStartResponse,
)

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


class AgentSessionNotFoundError(Exception):
    def __init__(self, session_id: int) -> None:
        self.session_id = session_id
        super().__init__(str(session_id))


class AgentSessionMismatchError(Exception):
    def __init__(self, session_id: int) -> None:
        self.session_id = session_id
        super().__init__(str(session_id))


class DraftAgentRuntimeConfig:
    """Adapter that lets a draft Agent config flow through `AgentRuntime`.

    Matches `AgentVersionLike` so the runtime can resolve the model and tools
    without persisting a published version.
    """

    def __init__(self, draft: AgentDraftConfig) -> None:
        self.model = draft.model
        self.system_prompt = draft.system_prompt
        self.provider_id = draft.provider_id
        self.model_config: LlmModelParameters | dict[str, object] | None = (
            draft.model_parameters
        )
        self.tool_allowlist = list(draft.tool_allowlist)
        self.mcp_server_ids = list(draft.mcp_server_ids)


class SessionRepositoryLike(Protocol):
    async def create_session(self, title=None, thread_id=None): ...
    async def get_session(self, session_id: int): ...
    async def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        additional_kwargs=None,
    ): ...
    async def get_messages_after(
        self,
        session_id: int,
        after: int = 0,
        limit: int = 100,
    ): ...


class SessionBroadcastLike(Protocol):
    async def publish(self, session_id: int, message: dict[str, object]) -> None: ...


class AgentService:
    def __init__(
        self,
        repository: AgentRepository,
        commit: Committer | None = None,
        *,
        session_repository: SessionRepositoryLike | None = None,
        session_broadcast: SessionBroadcastLike | None = None,
        schedule_agent_run: Callable[[int, UUID], object] | None = None,
    ) -> None:
        self._repository = repository
        self._commit = commit
        self._session_repository = session_repository
        self._session_broadcast = session_broadcast
        self._schedule_agent_run = schedule_agent_run

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

    async def start_draft_session(
        self,
        agent_id: UUID,
        request: AgentSessionStart,
    ) -> AgentSessionStartResponse:
        if self._session_repository is None:
            raise RuntimeError("Session repository is not configured.")

        agent = await self._require_agent(agent_id)
        if not agent.enabled:
            raise AgentDisabledError(agent_id)
        draft = validate_draft_config(agent.draft_config, agent_id=agent_id)

        if request.session_id is None:
            session = await self._session_repository.create_session(
                title=f"Agent {agent_id} draft",
            )
            session_id = int(session.id)
        else:
            session = await self._session_repository.get_session(request.session_id)
            if session is None:
                raise AgentSessionNotFoundError(request.session_id)
            existing_messages = await self._session_repository.get_messages_after(
                request.session_id, after=0, limit=1
            )
            if existing_messages:
                first = existing_messages[0]
                first_kwargs = getattr(first, "additional_kwargs", None) or (
                    first.get("additional_kwargs", {})
                    if isinstance(first, dict)
                    else {}
                )
                if first_kwargs.get("agent_id") != str(agent_id):
                    raise AgentSessionMismatchError(request.session_id)
            session_id = int(request.session_id)

        await self._session_repository.append_message(
            session_id,
            role="user",
            content=request.message,
            additional_kwargs={"agent_id": str(agent_id)},
        )
        await self._commit_if_configured()

        # touch the draft so callers can detect drift at run time.
        _ = draft

        if self._schedule_agent_run is not None:
            self._schedule_agent_run(session_id, agent_id)

        return AgentSessionStartResponse(
            session_id=session_id,
            stream_url=f"/api/sessions/{session_id}/stream?after=0",
        )

    async def _require_agent(self, agent_id: UUID) -> Agent:
        agent = await self._repository.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        return agent

    def _draft_update_kwargs(self, request: AgentDraftUpdate) -> dict[str, object]:
        fields_set = request.model_fields_set
        kwargs: dict[str, object] = {}
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

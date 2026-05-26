import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.models.agents import Agent, AgentVersion
from app.repositories.agents import (
    AgentNotFoundError,
    AgentRepository,
    AgentVersionNotFoundError,
)
from app.repositories.runs import RunRepository
from app.schemas.agents import AgentCreate, AgentDraftUpdate, AgentTestRunCreate
from app.schemas.runs import RunStatus

Committer = Callable[[], object]
Scheduler = Callable[[UUID], object]
MISSING_AGENT_VERSION_ID = UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True)
class AgentRunStartResult:
    accepted: bool
    status_url: str
    events_url: str
    run_id: UUID
    status: RunStatus


class AgentService:
    def __init__(
        self,
        repository: AgentRepository,
        commit: Committer | None = None,
        run_repository: RunRepository | None = None,
        schedule_test_run: Scheduler | None = None,
    ) -> None:
        self._repository = repository
        self._commit = commit
        self._run_repository = run_repository
        self._schedule_test_run = schedule_test_run

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

    async def start_test_run(
        self,
        agent_key: str,
        request: AgentTestRunCreate,
    ) -> AgentRunStartResult:
        if self._run_repository is None:
            raise RuntimeError("Agent test run repository is not configured.")

        agent = await self._repository.get_agent(agent_key)
        if agent is None or not agent.enabled:
            raise AgentNotFoundError(agent_key)

        version = await self._resolve_test_run_version(agent, request)
        messages = [message.model_dump(mode="json") for message in request.messages]
        run = await self._run_repository.create_agent_test_run(
            agent_key=agent_key,
            agent_version=version,
            messages=messages,
            input_preview=_input_preview(messages),
        )
        await self._commit_if_configured()
        await self._schedule_test_run_if_configured(run.id)
        return AgentRunStartResult(
            accepted=True,
            run_id=run.id,
            status=RunStatus.pending,
            status_url=f"/api/runs/{run.id}",
            events_url=f"/api/runs/{run.id}/events",
        )

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

    async def _resolve_test_run_version(
        self,
        agent: Agent,
        request: AgentTestRunCreate,
    ) -> AgentVersion:
        if request.version_id is not None:
            version = await self._repository.get_version_by_id(request.version_id)
            if version is None or version.agent_id != agent.id:
                raise AgentVersionNotFoundError(request.version_id)
            return version

        if request.version_number is not None:
            version = await self._repository.get_version_by_number(
                agent.key,
                request.version_number,
            )
            if version is None or version.agent_id != agent.id:
                raise AgentVersionNotFoundError(MISSING_AGENT_VERSION_ID)
            return version

        if agent.latest_version is None:
            raise AgentVersionNotFoundError(MISSING_AGENT_VERSION_ID)
        return agent.latest_version

    async def _commit_if_configured(self) -> None:
        if self._commit is None:
            return
        result = self._commit()
        if inspect.isawaitable(result):
            await result

    async def _schedule_test_run_if_configured(self, run_id: UUID) -> None:
        if self._schedule_test_run is None:
            return
        result = self._schedule_test_run(run_id)
        if inspect.isawaitable(result):
            await result


async def run_agent_test_with_new_session(run_id: UUID) -> None:
    return None


def _input_preview(messages: list[dict[str, str]]) -> str:
    if not messages:
        return ""
    user_message = next(
        (message for message in messages if message.get("role") == "user"),
        messages[0],
    )
    return user_message.get("content", "")[:200]

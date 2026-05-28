import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.agent_runtime import AgentRuntime, to_jsonable
from app.core.agent_streaming import consume_runtime_stream
from app.core.database import async_session
from app.core.llm_models import LlmProviderRuntimeConfig
from app.models.agents import Agent, AgentVersion
from app.repositories.agents import (
    AgentDisabledError,
    AgentNotFoundError,
    AgentRepository,
    AgentVersionNotFoundError,
)
from app.repositories.llm_providers import (
    LlmProviderNotFoundError,
    LlmProviderRepository,
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
        run_repository: RunRepository | None = None,
        schedule_test_run: Scheduler | None = None,
    ) -> None:
        self._repository = repository
        self._commit = commit
        self._run_repository = run_repository
        self._schedule_test_run = schedule_test_run

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

    async def delete_agent(self, agent_id: UUID) -> Agent:
        agent = await self._repository.soft_delete(agent_id)
        await self._commit_if_configured()
        return agent

    async def start_test_run(
        self,
        agent_id: UUID,
        request: AgentTestRunCreate,
    ) -> AgentRunStartResult:
        if self._run_repository is None:
            raise RuntimeError("Agent test run repository is not configured.")

        agent = await self._repository.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        if not agent.enabled:
            raise AgentDisabledError(agent_id)

        version = await self._resolve_test_run_version(agent, request)
        messages = [message.model_dump(mode="json") for message in request.messages]
        run = await self._run_repository.create_agent_test_run(
            agent_id=agent.id,
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
                agent.id,
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


async def run_agent_test(
    run_id: UUID,
    run_repository: RunRepository,
    agent_repository: AgentRepository,
    runtime: AgentRuntime | None = None,
) -> dict[str, Any]:
    run = await run_repository.mark_running(run_id)
    runtime = runtime or AgentRuntime()

    try:
        version_id = _agent_version_id(run)
        version = await agent_repository.get_version_by_id(version_id)
        if version is None:
            error = {
                "type": "AgentVersionNotFound",
                "message": f"Agent version not found: {version_id}",
            }
            await _append_error_event(run_repository, run, error)
            await run_repository.mark_terminal(
                run_id,
                RunStatus.error,
                error=error,
                result_status="error",
            )
            await _commit_if_available(run_repository)
            return {"status": "error", "error": error}

        await run_repository.append_event(
            run_id,
            event_type="custom",
            thread_id=run.thread_id,
            payload={
                "message": "Started agent test run.",
                "agent_id": _agent_id(run),
                "agent_version_number": version.version_number,
            },
            node="start",
        )
        await _commit_if_available(run_repository)
        input_messages = list(run.subject_snapshot.get("messages", []))
        stream = getattr(runtime, "stream", None)
        if stream is not None:
            events = stream(version=version, messages=input_messages)
            if inspect.isawaitable(events):
                events = await events
            stream_result = await consume_runtime_stream(
                run_repository,
                run,
                events,
            )
            if stream_result.error is not None:
                await run_repository.mark_terminal(
                    run_id,
                    RunStatus.error,
                    error=stream_result.error,
                    result_status="error",
                )
                await _commit_if_available(run_repository)
                return {"status": "error", "error": stream_result.error}
            result_messages = stream_result.messages
            raw_graph_output = stream_result.raw_graph_output
        else:
            result = await runtime.run(
                version=version,
                messages=input_messages,
            )
            result_messages = to_jsonable(result.messages)
            raw_graph_output = to_jsonable(result.raw_output)
            await run_repository.append_event(
                run_id,
                event_type="messages",
                thread_id=run.thread_id,
                payload={"messages": result_messages},
                node="agent",
            )
        if stream is None or not stream_result.done_seen:
            await run_repository.append_event(
                run_id,
                event_type="done",
                thread_id=run.thread_id,
                payload={"status": "done", "result_status": "success"},
            )
        await run_repository.mark_terminal(
            run_id,
            RunStatus.success,
            structured_result={"messages": result_messages},
            raw_graph_output=raw_graph_output,
            result_status="success",
        )
        await _commit_if_available(run_repository)
        return {"status": "success", "messages": result_messages}
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        await _append_error_event(run_repository, run, error)
        await run_repository.mark_terminal(
            run_id,
            RunStatus.error,
            error=error,
            result_status="error",
        )
        await _commit_if_available(run_repository)
        return {"status": "error", "error": error}


async def run_agent_test_with_new_session(run_id: UUID) -> dict[str, Any]:
    async with async_session() as session:
        run_repository = RunRepository(session)
        agent_repository = AgentRepository(session)
        provider_repository = LlmProviderRepository(session)
        runtime = AgentRuntime(
            provider_resolver=DatabaseLlmProviderResolver(provider_repository)
        )
        return await run_agent_test(run_id, run_repository, agent_repository, runtime)


def _input_preview(messages: list[dict[str, str]]) -> str:
    if not messages:
        return ""
    user_message = next(
        (message for message in messages if message.get("role") == "user"),
        messages[0],
    )
    return user_message.get("content", "")[:200]


def _agent_version_id(run: Any) -> UUID:
    return UUID(str(run.metadata_["agent_version_id"]))


def _agent_id(run: Any) -> str:
    return str(run.metadata_.get("agent_id") or run.subject_id)


async def _append_error_event(
    repository: RunRepository,
    run: Any,
    error: dict[str, Any],
) -> None:
    await repository.append_event(
        run.id,
        event_type="error",
        thread_id=run.thread_id,
        payload=error,
    )


async def _commit_if_available(repository: RunRepository) -> None:
    commit = getattr(repository, "commit", None)
    if commit is None:
        return
    result = commit()
    if inspect.isawaitable(result):
        await result

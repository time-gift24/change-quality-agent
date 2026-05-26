import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from agent.react_runtime import AgentRuntime, to_jsonable
from app.core.database import async_session
from app.models.agents import Agent, AgentVersion
from app.repositories.agents import (
    AgentDisabledError,
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


@dataclass(frozen=True)
class RuntimeStreamResult:
    messages: list[dict[str, Any]]
    raw_graph_output: dict[str, Any]
    done_seen: bool
    error: dict[str, Any] | None = None


SUPPORTED_STREAM_EVENT_TYPES = {
    "tasks",
    "messages",
    "updates",
    "custom",
    "checkpoints",
    "error",
    "done",
}


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
        if agent is None:
            raise AgentNotFoundError(agent_key)
        if not agent.enabled:
            raise AgentDisabledError(agent_key)

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
                "agent_key": _agent_key(run),
                "agent_version_number": version.version_number,
            },
            node="start",
        )
        await _commit_if_available(run_repository)
        input_messages = list(run.subject_snapshot.get("messages", []))
        stream = getattr(runtime, "stream", None)
        if stream is not None:
            stream_result = await _consume_runtime_stream(
                run_repository,
                run,
                stream,
                version=version,
                messages=input_messages,
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
        return await run_agent_test(run_id, run_repository, agent_repository)


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


def _agent_key(run: Any) -> str:
    return str(run.metadata_.get("agent_key") or run.subject_id)


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


async def _consume_runtime_stream(
    repository: RunRepository,
    run: Any,
    stream: Callable[..., Any],
    *,
    version: Any,
    messages: list[dict[str, Any]],
) -> RuntimeStreamResult:
    result_messages: list[dict[str, Any]] = []
    message_deltas: list[str] = []
    raw_events: list[Any] = []
    done_seen = False
    stream_error: dict[str, Any] | None = None
    events = stream(version=version, messages=messages)
    if inspect.isawaitable(events):
        events = await events

    async for event in events:
        json_event = to_jsonable(event)
        raw_events.append(json_event)
        event_parts = _stream_event_parts(json_event)
        if event_parts is None:
            continue

        await repository.append_event(
            run.id,
            event_type=event_parts["event_type"],
            thread_id=run.thread_id,
            payload=event_parts["payload"],
            node=event_parts["node"],
            checkpoint_id=event_parts["checkpoint_id"],
            task_id=event_parts["task_id"],
        )
        await _commit_if_available(repository)

        payload = event_parts["payload"]
        if event_parts["event_type"] == "done":
            done_seen = True
        if event_parts["event_type"] == "error":
            stream_error = _stream_error_payload(payload)
        if isinstance(payload.get("delta"), str):
            message_deltas.append(payload["delta"])
        if isinstance(payload.get("messages"), list):
            result_messages = to_jsonable(payload["messages"])

    if not result_messages and message_deltas:
        result_messages = [
            {"role": "assistant", "content": "".join(message_deltas)},
        ]

    return RuntimeStreamResult(
        messages=result_messages,
        raw_graph_output={"stream_events": raw_events},
        done_seen=done_seen,
        error=stream_error,
    )


def _stream_event_parts(event: Any) -> dict[str, Any] | None:
    if not isinstance(event, Mapping):
        return None

    event_type = event.get("type")
    payload = event.get("payload")
    if not isinstance(event_type, str) or not isinstance(payload, Mapping):
        return None
    if event_type not in SUPPORTED_STREAM_EVENT_TYPES:
        event_type = "custom"

    return {
        "event_type": event_type,
        "payload": dict(payload),
        "node": _optional_str(event.get("node")),
        "checkpoint_id": _optional_str(event.get("checkpoint_id")),
        "task_id": _optional_str(event.get("task_id")),
    }


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _stream_error_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    error = payload.get("error")
    source = error if isinstance(error, Mapping) else payload
    error_type = source.get("type")
    message = source.get("message")
    return {
        "type": error_type if isinstance(error_type, str) else "StreamError",
        "message": message if isinstance(message, str) else "Stream failed.",
    }

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.agent.sop_quality import SOP_QUALITY_AGENT_KEY, stream_sop_quality_agent
from app.core.agent_runtime import AgentRuntime
from app.core.agent_streaming import consume_runtime_stream
from app.core.config import Settings
from app.core.database import async_session
from app.repositories.agents import AgentRepository
from app.repositories.runs import ActiveRunExistsError, RunRepository
from app.schemas.runs import RunStatus
from app.services.sop_client import SopClient


@dataclass(frozen=True)
class RunStartResult:
    accepted: bool
    status_url: str
    events_url: str
    run_id: UUID | None = None
    active_run_id: UUID | None = None
    status: RunStatus | None = None
    message: str | None = None


Scheduler = Callable[[UUID], object]
Committer = Callable[[], Awaitable[None]]


async def _noop_commit() -> None:
    return None


class SopQualityService:
    def __init__(
        self,
        *,
        settings: Settings,
        sop_client: SopClient,
        repository: RunRepository,
        schedule_run: Scheduler | None = None,
        commit: Committer = _noop_commit,
    ) -> None:
        self._settings = settings
        self._sop_client = sop_client
        self._repository = repository
        self._schedule_run = schedule_run
        self._commit = commit

    async def start_run(
        self,
        sop_id: str,
        env_key: str,
        created_by: str | None = None,
    ) -> RunStartResult:
        environment = self._settings.get_environment(env_key)
        sop_snapshot = await self._sop_client.get_sop(sop_id, env_key)
        active_conflict_key = f"sop:{sop_id}:env:{env_key}"

        try:
            run = await self._repository.create_sop_run(
                sop_id=sop_id,
                env_key=env_key,
                env_snapshot=environment.public_dict(),
                sop_snapshot=sop_snapshot.model_dump(mode="json"),
                active_conflict_key=active_conflict_key,
                created_by=created_by,
            )
        except ActiveRunExistsError as exc:
            return self._conflict_result(exc.active_run_id)

        await self._commit()
        await self._schedule_if_configured(run.id)
        return RunStartResult(
            accepted=True,
            run_id=run.id,
            status=RunStatus.pending,
            status_url=f"/api/runs/{run.id}",
            events_url=f"/api/runs/{run.id}/events",
        )

    async def _schedule_if_configured(self, run_id: UUID) -> None:
        if self._schedule_run is None:
            return
        result = self._schedule_run(run_id)
        if inspect.isawaitable(result):
            await result

    def _conflict_result(self, active_run_id: UUID) -> RunStartResult:
        return RunStartResult(
            accepted=False,
            active_run_id=active_run_id,
            status=RunStatus.running,
            message="An active run already exists for this SOP and environment.",
            status_url=f"/api/runs/{active_run_id}",
            events_url=f"/api/runs/{active_run_id}/events",
        )


async def run_sop_quality_graph(
    run_id: UUID,
    repository: RunRepository,
    *,
    agent_repository: AgentRepository | None = None,
    runtime: AgentRuntime | None = None,
    agent_key: str = SOP_QUALITY_AGENT_KEY,
) -> dict[str, Any]:
    run = await repository.mark_running(run_id)
    runtime = runtime or AgentRuntime()
    try:
        if agent_repository is None:
            raise RuntimeError("SOP quality agent repository is not configured.")
        agent = await agent_repository.get_agent(agent_key)
        if agent is None:
            raise RuntimeError(f"SOP quality agent not found: {agent_key}")
        if not agent.enabled:
            raise RuntimeError(f"SOP quality agent is disabled: {agent_key}")
        version = agent.latest_version
        if version is None:
            raise RuntimeError(f"SOP quality agent has no published version: {agent_key}")

        await repository.append_event(
            run_id,
            event_type="custom",
            thread_id=run.thread_id,
            payload={
                "message": "Started SOP quality agent.",
                "agent_key": agent_key,
                "agent_version_number": version.version_number,
            },
            node="start",
        )
        await _commit_if_available(repository)

        stream = getattr(runtime, "stream", None)
        if stream is None:
            raise RuntimeError("SOP quality agent runtime does not support streaming.")
        stream_result = await consume_runtime_stream(
            repository,
            run,
            stream_sop_quality_agent(runtime=runtime, version=version, run=run),
        )
        if stream_result.error is not None:
            await repository.mark_terminal(
                run_id,
                RunStatus.error,
                error=stream_result.error,
                result_status="error",
            )
            await _commit_if_available(repository)
            return {"status": "error", "error": stream_result.error}

        if not stream_result.done_seen:
            await repository.append_event(
                run_id,
                event_type="done",
                thread_id=run.thread_id,
                payload={"status": "done", "result_status": "success"},
            )
        await repository.mark_terminal(
            run_id,
            RunStatus.success,
            raw_graph_output=stream_result.raw_graph_output,
            structured_result={"messages": stream_result.messages},
            result_status="success",
        )
        await _commit_if_available(repository)
        return {
            "status": "success",
            "messages": stream_result.messages,
            "raw_graph_output": stream_result.raw_graph_output,
        }
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        await repository.append_event(
            run_id,
            event_type="error",
            thread_id=run.thread_id,
            payload=error,
        )
        await repository.mark_terminal(
            run_id,
            RunStatus.error,
            error=error,
            result_status="error",
        )
        await _commit_if_available(repository)
        return {"status": "error", "error": error}


async def run_sop_quality_graph_with_new_session(run_id: UUID) -> dict[str, Any]:
    async with async_session() as session:
        repository = RunRepository(session)
        agent_repository = AgentRepository(session)
        return await run_sop_quality_graph(
            run_id,
            repository,
            agent_repository=agent_repository,
        )


async def _commit_if_available(repository: RunRepository) -> None:
    commit = getattr(repository, "commit", None)
    if commit is not None:
        await commit()

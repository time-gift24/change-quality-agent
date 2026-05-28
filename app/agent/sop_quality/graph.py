from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from app.agent.sop_quality.prompts.system_prompts import build_sop_quality_user_message
from app.core.agent_runtime import AgentRuntime
from app.core.agent_streaming import consume_runtime_stream
from app.core.config import settings
from app.core.database import async_session
from app.repositories.agents import AgentRepository
from app.repositories.runs import RunRepository
from app.schemas.runs import RunStatus

SOP_QUALITY_AGENT_KEY = "sop-quality-v1"


async def stream_sop_quality_agent(
    *,
    runtime: AgentRuntime,
    version: Any,
    run: Any,
) -> AsyncIterator[dict[str, Any]]:
    messages = [build_sop_quality_user_message(run)]
    async for event in runtime.stream(version=version, messages=messages):
        yield event


async def run_sop_quality_graph(
    run_id: UUID,
    repository: RunRepository,
    *,
    agent_repository: AgentRepository | None = None,
    runtime: AgentRuntime | None = None,
    agent_id: UUID | None = None,
) -> dict[str, Any]:
    run = await repository.mark_running(run_id)
    runtime = runtime or AgentRuntime()
    try:
        if agent_repository is None:
            raise RuntimeError("SOP quality agent repository is not configured.")
        resolved_agent_id = agent_id or _configured_sop_quality_agent_id()
        agent = await agent_repository.get_agent(resolved_agent_id)
        if agent is None:
            raise RuntimeError(f"SOP quality agent not found: {resolved_agent_id}")
        if not agent.enabled:
            raise RuntimeError(f"SOP quality agent is disabled: {resolved_agent_id}")
        version = agent.latest_version
        if version is None:
            raise RuntimeError(
                f"SOP quality agent has no published version: {resolved_agent_id}"
            )

        await repository.append_event(
            run_id,
            event_type="custom",
            thread_id=run.thread_id,
            payload={
                "message": "Started SOP quality agent.",
                "agent_id": str(resolved_agent_id),
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


def _configured_sop_quality_agent_id() -> UUID:
    if not settings.sop_quality_agent_id:
        raise RuntimeError("SOP_QUALITY_AGENT_ID is required.")
    return UUID(settings.sop_quality_agent_id)

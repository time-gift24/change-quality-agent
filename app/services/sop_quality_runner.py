from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.agent.manager.agent_factory import AgentFactory
from app.agent.sop_quality.graph import build_sop_quality_graph
from app.core.agent_streaming import DeepAgentStreamRunner
from app.core.checkpoints import open_postgres_checkpointer
from app.core.database import async_session
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.services.session_messages import RepositorySessionMessageWriter
from app.services.session_streaming import SessionBroadcast
from app.services.sop_client import MockSopClient
from app.services.sop_quality_streaming import SopQualityBroadcast

# LangGraph treats non-empty checkpoint namespaces as subgraph paths.
TOP_LEVEL_CHECKPOINT_NS = ""


@dataclass(frozen=True)
class _GraphRuntime:
    graph: Any
    config: dict[str, Any]
    session_id: int | None


async def run_sop_quality_check(
    check_id: UUID,
    repository: SopQualityCheckRepository,
    *,
    checkpointer: Any,
    llm_provider_repository: Any,
    sop_client: Any,
    submit_quality_result: Any,
    session_repository: Any | None = None,
    broadcast: SopQualityBroadcast | None = None,
    session_broadcast: SessionBroadcast | None = None,
) -> dict[str, Any]:
    try:
        check = await _mark_started(repository, check_id, broadcast)
        if check is None:
            return {"status": "skipped"}
        runtime = _build_graph_runtime(
            check=check,
            checkpointer=checkpointer,
            llm_provider_repository=llm_provider_repository,
            sop_client=sop_client,
            submit_quality_result=submit_quality_result,
            session_repository=session_repository,
            session_broadcast=session_broadcast,
        )
        final_state = await _invoke_graph(runtime, check)
        await _save_latest_checkpoint(
            repository,
            check_id,
            runtime,
            checkpointer,
            broadcast,
        )
        await _mark_succeeded(
            repository,
            check_id,
            final_state,
            session_id=runtime.session_id,
            session_repository=session_repository,
            broadcast=broadcast,
        )
        return {"status": "succeeded", "result": final_state.get("result")}
    except Exception as exc:
        return await _mark_failed(
            repository,
            check_id,
            exc,
            broadcast=broadcast,
            session_repository=session_repository,
        )


async def _mark_started(
    repository: SopQualityCheckRepository,
    check_id: UUID,
    broadcast: SopQualityBroadcast | None,
) -> Any | None:
    check = await repository.mark_running(check_id)
    if check is None:
        return None
    started_event = await repository.append_event(
        check_id,
        event_type="started",
        message="SOP quality check started.",
    )
    await repository.commit()
    await _publish_event(broadcast, check_id, started_event)
    return check


def _build_graph_runtime(
    *,
    check: Any,
    checkpointer: Any,
    llm_provider_repository: Any,
    sop_client: Any,
    submit_quality_result: Any,
    session_repository: Any | None,
    session_broadcast: SessionBroadcast | None,
) -> _GraphRuntime:
    session_id = getattr(check, "session_id", None)
    message_writer = _build_message_writer(
        session_repository=session_repository,
        session_id=session_id,
        session_broadcast=session_broadcast,
    )
    live_event_publisher = _session_live_event_publisher(session_broadcast, session_id)
    graph = build_sop_quality_graph(
        checkpointer=checkpointer,
        agent_factory=AgentFactory(llm_provider_repository),
        sop_client=sop_client,
        submit_quality_result=submit_quality_result,
        message_writer=message_writer,
        deepagent_stream_runner=DeepAgentStreamRunner(
            message_writer=message_writer,
            live_event_publisher=live_event_publisher,
            session_id=session_id,
        ),
        live_event_publisher=live_event_publisher,
    )
    return _GraphRuntime(
        graph=graph,
        config=_top_level_checkpoint_config(check.thread_id),
        session_id=session_id,
    )


async def _invoke_graph(runtime: _GraphRuntime, check: Any) -> dict[str, Any]:
    initial_state = {
        "check_id": str(check.id),
        "sop_id": check.sop_id,
        "env_key": check.env_key,
    }
    return await runtime.graph.ainvoke(initial_state, config=runtime.config)


async def _save_latest_checkpoint(
    repository: SopQualityCheckRepository,
    check_id: UUID,
    runtime: _GraphRuntime,
    checkpointer: Any,
    broadcast: SopQualityBroadcast | None,
) -> None:
    checkpoint_id = await _latest_checkpoint_id(
        runtime.graph,
        runtime.config,
        checkpointer,
    )
    if checkpoint_id is None:
        return
    await repository.set_current_checkpoint(check_id, checkpoint_id)
    checkpoint_event = await repository.append_event(
        check_id,
        event_type="checkpoint",
        checkpoint_id=checkpoint_id,
        message="Checkpoint saved.",
    )
    await repository.commit()
    await _publish_event(broadcast, check_id, checkpoint_event)


async def _mark_succeeded(
    repository: SopQualityCheckRepository,
    check_id: UUID,
    final_state: dict[str, Any],
    *,
    session_id: int | None,
    session_repository: Any | None,
    broadcast: SopQualityBroadcast | None,
) -> None:
    await repository.mark_terminal(
        check_id,
        "succeeded",
        quality_result=final_state.get("quality_result"),
        result=final_state.get("result"),
    )
    if session_repository is not None and session_id is not None:
        await session_repository.set_status(session_id, "completed")
    completed_event = await repository.append_event(
        check_id,
        event_type="completed",
        message="SOP quality check completed.",
    )
    await repository.commit()
    await _publish_event(broadcast, check_id, completed_event)


async def run_sop_quality_check_with_new_session(
    check_id: UUID,
    broadcast: SopQualityBroadcast | None = None,
    session_broadcast: SessionBroadcast | None = None,
) -> dict[str, Any]:
    async with async_session() as session:
        repository = SopQualityCheckRepository(session)
        session_repository = SessionRepository(session)
        llm_provider_repository = LlmProviderRepository(session)
        try:
            async with open_postgres_checkpointer(setup=True) as checkpointer:
                return await run_sop_quality_check(
                    check_id,
                    repository,
                    checkpointer=checkpointer,
                    llm_provider_repository=llm_provider_repository,
                    sop_client=MockSopClient(),
                    submit_quality_result=_mock_external_submit,
                    session_repository=session_repository,
                    broadcast=broadcast,
                    session_broadcast=session_broadcast,
                )
        except Exception as exc:
            return await _mark_failed(
                repository,
                check_id,
                exc,
                broadcast=broadcast,
                session_repository=session_repository,
            )


def _build_message_writer(
    *,
    session_repository: Any | None,
    session_id: int | None,
    session_broadcast: SessionBroadcast | None,
) -> object:
    if session_repository is None or session_id is None:
        return _NoopMessageWriter()
    return RepositorySessionMessageWriter(
        repository=session_repository,
        session_id=session_id,
        broadcast=session_broadcast,
        commit=getattr(session_repository, "commit", None),
    )


class _NoopMessageWriter:
    async def append_step_message(
        self,
        *,
        step: str,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        class _Msg:
            sequence = 0

        return _Msg()


async def _latest_checkpoint_id(
    graph: Any,
    config: dict[str, Any],
    checkpointer: Any,
) -> str | None:
    if checkpointer is None:
        return None
    snapshot = await graph.aget_state(config)
    return _checkpoint_id_from_config(snapshot.config)


def _checkpoint_id_from_config(config: dict[str, Any] | None) -> str | None:
    configurable = (config or {}).get("configurable")
    if not isinstance(configurable, dict):
        return None
    checkpoint_id = configurable.get("checkpoint_id")
    return checkpoint_id if isinstance(checkpoint_id, str) else None


async def _mark_failed(
    repository: SopQualityCheckRepository,
    check_id: UUID,
    exc: Exception,
    *,
    broadcast: SopQualityBroadcast | None = None,
    session_repository: Any | None = None,
) -> dict[str, Any]:
    error = {"type": type(exc).__name__, "message": str(exc)}
    check = await repository.get_check(check_id)
    await repository.mark_terminal(check_id, "failed", error=error)
    session_id = getattr(check, "session_id", None) if check is not None else None
    if session_repository is not None and session_id is not None:
        await session_repository.set_status(session_id, "failed")
    failed_event = await repository.append_event(
        check_id,
        event_type="failed",
        message=str(exc),
    )
    await repository.commit()
    await _publish_event(broadcast, check_id, failed_event)
    return {"status": "failed", "error": error}


async def _mock_external_submit(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_status": "mock_submitted",
        "check_id": payload.get("check_id"),
    }


async def _publish_event(
    broadcast: SopQualityBroadcast | None,
    check_id: UUID,
    event: Any,
) -> None:
    if broadcast is None:
        return
    await broadcast.publish(check_id, _event_to_message(event))


def _session_live_event_publisher(
    session_broadcast: SessionBroadcast | None,
    session_id: int | None,
) -> object:
    if session_broadcast is None or session_id is None:
        return None

    async def publish(event: dict[str, Any]) -> None:
        await session_broadcast.publish(
            session_id,
            {
                **event,
                "session_id": session_id,
            },
        )

    return publish


def _event_to_message(event: Any) -> dict[str, Any]:
    return {
        "check_id": event.check_id,
        "sequence": event.sequence,
        "type": event.type,
        "node": getattr(event, "node", None),
        "checkpoint_id": getattr(event, "checkpoint_id", None),
        "task_id": getattr(event, "task_id", None),
        "message": getattr(event, "message", None),
        "created_at": getattr(event, "created_at", None),
    }


def _top_level_checkpoint_config(thread_id: str) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": TOP_LEVEL_CHECKPOINT_NS,
        }
    }

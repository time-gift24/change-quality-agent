from typing import Protocol
from uuid import UUID

from app.agent.manager.agent_factory import AgentFactory
from app.agent.sop_quality.graph import build_sop_quality_graph
from app.agent.sop_quality.nodes.submit_result import SubmitQualityResult
from app.core.agent_streaming import (
    DeepAgentStreamRunner,
    LiveEventPublisher,
    SessionMessageWriter,
)
from app.core.checkpoints import open_postgres_checkpointer
from app.core.database import async_session
from app.core.json_types import JsonObject
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.services.session_messages import RepositorySessionMessageWriter
from app.services.session_streaming import SessionBroadcast
from app.services.sop_client import MockSopClient, SopClient
from app.services.sop_quality_streaming import SopQualityBroadcast

# LangGraph treats non-empty checkpoint namespaces as subgraph paths.
TOP_LEVEL_CHECKPOINT_NS = ""


class _GraphSnapshotLike(Protocol):
    config: dict[str, object] | None


class _GraphLike(Protocol):
    async def ainvoke(
        self,
        initial_state: JsonObject,
        *,
        config: JsonObject,
    ) -> JsonObject:
        ...

    async def aget_state(self, config: JsonObject) -> _GraphSnapshotLike:
        ...


async def run_sop_quality_check(
    check_id: UUID,
    repository: SopQualityCheckRepository,
    *,
    checkpointer: object | None,
    llm_provider_repository: LlmProviderRepository,
    sop_client: SopClient,
    submit_quality_result: SubmitQualityResult,
    session_repository: SessionRepository | None = None,
    broadcast: SopQualityBroadcast | None = None,
    session_broadcast: SessionBroadcast | None = None,
) -> dict[str, object]:
    try:
        check = await repository.mark_running(check_id)
        if check is None:
            return {"status": "skipped"}
        started_event = await repository.append_event(
            check_id,
            event_type="started",
            message="SOP quality check started.",
        )
        await repository.commit()
        await _publish_event(broadcast, check_id, started_event)

        session_id = getattr(check, "session_id", None)
        message_writer = _build_message_writer(
            session_repository=session_repository,
            session_id=session_id,
            session_broadcast=session_broadcast,
        )
        live_event_publisher = _session_live_event_publisher(
            session_broadcast,
            session_id,
        )
        deepagent_stream_runner = DeepAgentStreamRunner(
            message_writer=message_writer,
            live_event_publisher=live_event_publisher,
            session_id=session_id,
        )

        graph = build_sop_quality_graph(
            checkpointer=checkpointer,
            agent_factory=AgentFactory(llm_provider_repository),
            sop_client=sop_client,
            submit_quality_result=submit_quality_result,
            message_writer=message_writer,
            deepagent_stream_runner=deepagent_stream_runner,
            live_event_publisher=live_event_publisher,
        )
        config = _top_level_checkpoint_config(check.thread_id)
        initial_state: JsonObject = {
            "check_id": str(check.id),
            "sop_id": check.sop_id,
            "env_key": check.env_key,
        }

        final_state = await graph.ainvoke(initial_state, config=config)
        checkpoint_id = await _latest_checkpoint_id(graph, config, checkpointer)
        if checkpoint_id is not None:
            await repository.set_current_checkpoint(check_id, checkpoint_id)
            checkpoint_event = await repository.append_event(
                check_id,
                event_type="checkpoint",
                checkpoint_id=checkpoint_id,
                message="Checkpoint saved.",
            )
            await repository.commit()
            await _publish_event(broadcast, check_id, checkpoint_event)
        quality_result = final_state.get("quality_result")
        result = final_state.get("result")
        await repository.mark_terminal(
            check_id,
            "succeeded",
            quality_result=quality_result if isinstance(quality_result, str) else None,
            result=result if isinstance(result, dict) else None,
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
        return {"status": "succeeded", "result": final_state.get("result")}
    except Exception as exc:
        return await _mark_failed(
            repository,
            check_id,
            exc,
            broadcast=broadcast,
            session_repository=session_repository,
        )


async def run_sop_quality_check_with_new_session(
    check_id: UUID,
    broadcast: SopQualityBroadcast | None = None,
    session_broadcast: SessionBroadcast | None = None,
) -> dict[str, object]:
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
    session_repository: SessionRepository | None,
    session_id: int | None,
    session_broadcast: SessionBroadcast | None,
) -> SessionMessageWriter:
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
        additional_kwargs: JsonObject | None = None,
    ) -> object:
        class _Msg:
            sequence = 0

        return _Msg()


async def _latest_checkpoint_id(
    graph: _GraphLike,
    config: JsonObject,
    checkpointer: object | None,
) -> str | None:
    if checkpointer is None:
        return None
    snapshot = await graph.aget_state(config)
    return _checkpoint_id_from_config(snapshot.config)


def _checkpoint_id_from_config(config: dict[str, object] | None) -> str | None:
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
    session_repository: SessionRepository | None = None,
) -> dict[str, object]:
    error: JsonObject = {"type": type(exc).__name__, "message": str(exc)}
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


async def _mock_external_submit(payload: JsonObject) -> JsonObject:
    return {
        "external_status": "mock_submitted",
        "check_id": payload.get("check_id"),
    }


async def _publish_event(
    broadcast: SopQualityBroadcast | None,
    check_id: UUID,
    event: object,
) -> None:
    if broadcast is None:
        return
    await broadcast.publish(check_id, _event_to_message(event))


def _session_live_event_publisher(
    session_broadcast: SessionBroadcast | None,
    session_id: int | None,
) -> LiveEventPublisher | None:
    if session_broadcast is None or session_id is None:
        return None

    async def publish(event: JsonObject) -> None:
        await session_broadcast.publish(
            session_id,
            {
                **event,
                "session_id": session_id,
            },
        )

    return publish


def _event_to_message(event: object) -> dict[str, object]:
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


def _top_level_checkpoint_config(thread_id: str) -> JsonObject:
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": TOP_LEVEL_CHECKPOINT_NS,
        }
    }

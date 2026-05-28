from typing import Any
from uuid import UUID

from app.agent.sop_quality.graph import build_sop_quality_graph
from app.core.checkpoints import open_postgres_checkpointer
from app.core.database import async_session
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.services.sop_quality_streaming import SopQualityBroadcast

# LangGraph treats non-empty checkpoint namespaces as subgraph paths.
TOP_LEVEL_CHECKPOINT_NS = ""


async def run_sop_quality_check(
    check_id: UUID,
    repository: SopQualityCheckRepository,
    *,
    checkpointer: Any,
    llm_provider_repository: Any,
    broadcast: SopQualityBroadcast | None = None,
) -> dict[str, Any]:
    try:
        check = await repository.mark_running(check_id)
        started_event = await repository.append_event(
            check_id,
            event_type="started",
            message="SOP quality check started.",
        )
        await repository.commit()
        await _publish_event(broadcast, check_id, started_event)

        graph = build_sop_quality_graph(
            checkpointer=checkpointer,
            llm_provider_repository=llm_provider_repository,
            on_live_event=_live_event_publisher(
                broadcast,
                check_id,
                sequence=started_event.sequence,
            ),
        )
        config = _top_level_checkpoint_config(check.thread_id)
        initial_state = {
            "check_id": str(check.id),
            "sop_id": check.sop_id,
            "env_key": check.env_key,
            "sop_snapshot": check.sop_snapshot,
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
        await repository.mark_terminal(
            check_id,
            "succeeded",
            quality_result=final_state.get("quality_result"),
            result=final_state.get("result"),
        )
        completed_event = await repository.append_event(
            check_id,
            event_type="completed",
            message="SOP quality check completed.",
        )
        await repository.commit()
        await _publish_event(broadcast, check_id, completed_event)
        return {"status": "succeeded", "result": final_state.get("result")}
    except Exception as exc:
        return await _mark_failed(repository, check_id, exc, broadcast=broadcast)


async def run_sop_quality_check_with_new_session(
    check_id: UUID,
    broadcast: SopQualityBroadcast | None = None,
) -> dict[str, Any]:
    async with async_session() as session:
        repository = SopQualityCheckRepository(session)
        llm_provider_repository = LlmProviderRepository(session)
        try:
            async with open_postgres_checkpointer(setup=True) as checkpointer:
                return await run_sop_quality_check(
                    check_id,
                    repository,
                    checkpointer=checkpointer,
                    llm_provider_repository=llm_provider_repository,
                    broadcast=broadcast,
                )
        except Exception as exc:
            return await _mark_failed(repository, check_id, exc, broadcast=broadcast)


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
) -> dict[str, Any]:
    error = {"type": type(exc).__name__, "message": str(exc)}
    await repository.mark_terminal(check_id, "failed", error=error)
    failed_event = await repository.append_event(
        check_id,
        event_type="failed",
        message=str(exc),
    )
    await repository.commit()
    await _publish_event(broadcast, check_id, failed_event)
    return {"status": "failed", "error": error}


async def _publish_event(
    broadcast: SopQualityBroadcast | None,
    check_id: UUID,
    event: Any,
) -> None:
    if broadcast is None:
        return
    await broadcast.publish(check_id, _event_to_message(event))


def _live_event_publisher(
    broadcast: SopQualityBroadcast | None,
    check_id: UUID,
    *,
    sequence: int,
):
    async def publish(event: dict[str, Any]) -> None:
        if broadcast is None:
            return
        await broadcast.publish(
            check_id,
            {
                "check_id": check_id,
                "sequence": sequence,
                **event,
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

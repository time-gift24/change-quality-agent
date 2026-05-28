from typing import Any
from uuid import UUID

from app.agent.sop_quality.graph import build_sop_quality_graph
from app.core.checkpoints import open_postgres_checkpointer
from app.core.database import async_session
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.services.sop_quality_streaming import SopQualityBroadcast


async def run_sop_quality_check(
    check_id: UUID,
    repository: SopQualityCheckRepository,
    *,
    checkpointer: Any,
    broadcast: SopQualityBroadcast | None = None,
) -> dict[str, Any]:
    check = await repository.mark_running(check_id)
    await repository.append_event(
        check_id,
        event_type="started",
        message="SOP quality check started.",
    )
    await repository.commit()
    if broadcast is not None:
        await broadcast.publish(check_id, {"type": "started"})

    graph = build_sop_quality_graph(checkpointer=checkpointer)
    config = {
        "configurable": {
            "thread_id": check.thread_id,
            "checkpoint_ns": check.checkpoint_ns,
        }
    }
    initial_state = {
        "check_id": str(check.id),
        "sop_id": check.sop_id,
        "env_key": check.env_key,
        "sop_snapshot": check.sop_snapshot,
    }

    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        checkpoint_id = await _latest_checkpoint_id(graph, config, checkpointer)
        if checkpoint_id is not None:
            await repository.set_current_checkpoint(check_id, checkpoint_id)
            await repository.append_event(
                check_id,
                event_type="checkpoint",
                checkpoint_id=checkpoint_id,
                message="Checkpoint saved.",
            )
        await repository.mark_terminal(
            check_id,
            "succeeded",
            quality_result=final_state.get("quality_result"),
            result=final_state.get("result"),
        )
        await repository.append_event(
            check_id,
            event_type="completed",
            message="SOP quality check completed.",
        )
        await repository.commit()
        if broadcast is not None:
            await broadcast.publish(check_id, {"type": "completed"})
        return {"status": "succeeded", "result": final_state.get("result")}
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        await repository.mark_terminal(check_id, "failed", error=error)
        await repository.append_event(check_id, event_type="failed", message=str(exc))
        await repository.commit()
        if broadcast is not None:
            await broadcast.publish(check_id, {"type": "failed", "message": str(exc)})
        return {"status": "failed", "error": error}


async def run_sop_quality_check_with_new_session(
    check_id: UUID,
    broadcast: SopQualityBroadcast | None = None,
) -> dict[str, Any]:
    async with async_session() as session:
        repository = SopQualityCheckRepository(session)
        async with open_postgres_checkpointer(setup=True) as checkpointer:
            return await run_sop_quality_check(
                check_id,
                repository,
                checkpointer=checkpointer,
                broadcast=broadcast,
            )


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

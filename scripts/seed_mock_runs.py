"""Seed mock SOP runs + events into Postgres for end-to-end frontend testing."""

import asyncio
from uuid import UUID

from app.core.database import async_session
from app.repositories.runs import RunRepository
from app.schemas.runs import RunStatus

SOP_ID = "release-checklist"
ENV_KEY = "dev"

SOP_SNAPSHOT = {
    "sop_id": SOP_ID,
    "env_key": ENV_KEY,
    "source_version": "mock-1",
    "updated_at": "2026-05-26T00:00:00Z",
    "payload": {
        "title": "Release checklist",
        "steps": [
            {"id": "load_sop", "name": "Load SOP"},
            {"id": "check_steps", "name": "Check steps"},
            {"id": "summarize_result", "name": "Summarize result"},
        ],
    },
}

ENV_SNAPSHOT = {"key": ENV_KEY, "name_en": "Development", "name_zh": "开发"}


async def _seed_terminal_run(repo: RunRepository) -> UUID:
    run = await repo.create_sop_run(
        sop_id=SOP_ID,
        env_key=ENV_KEY,
        env_snapshot=ENV_SNAPSHOT,
        sop_snapshot=SOP_SNAPSHOT,
        active_conflict_key=f"seed-terminal:{SOP_ID}:{ENV_KEY}",
    )
    run_id = run.id
    thread_id = run.thread_id

    await repo.mark_running(run_id)

    async def emit(event_type: str, node: str | None, payload: dict) -> None:
        await repo.append_event(
            run_id,
            event_type=event_type,
            thread_id=thread_id,
            payload=payload,
            node=node,
        )

    await emit("custom", "start", {"message": "Started mock SOP quality graph."})

    await emit("tasks", "load_sop", {"status": "started"})
    for chunk in ("Loading ", "release ", "checklist..."):
        await emit("messages", "load_sop", {"delta": chunk})
    await emit("tasks", "load_sop", {"status": "completed"})
    await emit(
        "updates",
        "load_sop",
        {"value": {"steps_loaded": 3}, "status": "ok"},
    )

    await emit("tasks", "check_steps", {"status": "started"})
    for chunk in ("Validating ", "step 1... ", "step 2... ", "step 3... done."):
        await emit("messages", "check_steps", {"delta": chunk})
    await emit("tasks", "check_steps", {"status": "completed"})
    await emit("updates", "check_steps", {"value": {"checks_passed": 3}})

    await emit("tasks", "summarize_result", {"status": "started"})
    for chunk in ("All ", "checks ", "passed. ", "Release ", "is ready."):
        await emit("messages", "summarize_result", {"delta": chunk})
    await emit("tasks", "summarize_result", {"status": "completed"})
    await emit(
        "updates",
        "summarize_result",
        {"value": {"summary": "Release ready", "risk": "low"}},
    )

    await emit("done", None, {"status": "done", "result_status": "mock_success"})

    await repo.mark_terminal(
        run_id,
        RunStatus.success,
        result_status="mock_success",
        raw_graph_output={"status": "ok"},
    )
    return run_id


async def _seed_failed_run(repo: RunRepository) -> UUID:
    run = await repo.create_sop_run(
        sop_id=SOP_ID,
        env_key=ENV_KEY,
        env_snapshot=ENV_SNAPSHOT,
        sop_snapshot=SOP_SNAPSHOT,
        active_conflict_key=f"seed-error:{SOP_ID}:{ENV_KEY}",
    )
    run_id = run.id
    thread_id = run.thread_id

    await repo.mark_running(run_id)

    async def emit(event_type: str, node: str | None, payload: dict) -> None:
        await repo.append_event(
            run_id,
            event_type=event_type,
            thread_id=thread_id,
            payload=payload,
            node=node,
        )

    await emit("tasks", "load_sop", {"status": "started"})
    await emit("messages", "load_sop", {"delta": "Loading SOP from upstream..."})
    await emit(
        "tasks",
        "load_sop",
        {"status": "failed", "error": "SOP upstream returned 502."},
    )
    await emit(
        "error",
        "load_sop",
        {"error": "SOP upstream returned 502.", "type": "SopClientError"},
    )

    await repo.mark_terminal(
        run_id,
        RunStatus.error,
        result_status="error",
        error={"type": "SopClientError", "message": "SOP upstream returned 502."},
    )
    return run_id


async def main() -> None:
    async with async_session() as session:
        repo = RunRepository(session)
        terminal_run_id = await _seed_terminal_run(repo)
        failed_run_id = await _seed_failed_run(repo)
        await repo.commit()

    print(f"Seeded terminal run: {terminal_run_id}")
    print(f"Seeded failed run:   {failed_run_id}")


if __name__ == "__main__":
    asyncio.run(main())

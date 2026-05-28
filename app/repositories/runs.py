from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runs import Run, RunEvent
from app.schemas.runs import RunStatus

ACTIVE_STATUSES = {RunStatus.pending.value, RunStatus.running.value}


class ActiveRunExistsError(Exception):
    def __init__(self, active_run_id: UUID) -> None:
        self.active_run_id = active_run_id
        super().__init__(str(active_run_id))


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_sop_run(
        self,
        *,
        sop_id: str,
        env_key: str,
        env_snapshot: dict[str, str],
        sop_snapshot: dict[str, Any],
        active_conflict_key: str,
        created_by: str | None = None,
        assistant_id: str = "sop-quality-v1",
    ) -> Run:
        active_run = await self._get_active_run_by_conflict_key(active_conflict_key)
        if active_run is not None:
            raise ActiveRunExistsError(active_run.id)

        run = Run(
            thread_id=str(uuid4()),
            assistant_id=assistant_id,
            subject_type="sop",
            subject_id=sop_id,
            env_key=env_key,
            status=RunStatus.pending.value,
            active_conflict_key=active_conflict_key,
            metadata_={
                "subject_type": "sop",
                "subject_id": sop_id,
                "env_key": env_key,
                "env_snapshot": env_snapshot,
                "active_conflict_key": active_conflict_key,
            },
            kwargs={"sop_id": sop_id, "env_key": env_key},
            completed_nodes=[],
            subject_snapshot=sop_snapshot,
            created_by=created_by,
        )
        self._session.add(run)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            active_run = await self._get_active_run_by_conflict_key(
                active_conflict_key
            )
            if active_run is not None:
                raise ActiveRunExistsError(active_run.id) from exc
            raise
        return run

    async def create_agent_test_run(
        self,
        *,
        agent_id: UUID,
        agent_version: Any,
        messages: list[dict[str, Any]],
        input_preview: str,
        created_by: str | None = None,
        assistant_id: str = "react-agent-test-v1",
    ) -> Run:
        agent_id_text = str(agent_id)
        agent_version_id = str(agent_version.id)
        version_number = agent_version.version_number
        run = Run(
            thread_id=str(uuid4()),
            assistant_id=assistant_id,
            subject_type="agent_test",
            subject_id=agent_id_text,
            env_key=None,
            status=RunStatus.pending.value,
            active_conflict_key=None,
            metadata_={
                "subject_type": "agent_test",
                "subject_id": agent_id_text,
                "agent_id": agent_id_text,
                "agent_version_id": agent_version_id,
                "agent_version_number": version_number,
                "run_kind": "agent_test",
                "input_preview": input_preview,
            },
            kwargs={
                "agent_id": agent_id_text,
                "agent_version_id": agent_version_id,
                "agent_version_number": version_number,
            },
            completed_nodes=[],
            subject_snapshot={
                "messages": [dict(message) for message in messages],
                "agent_version": _agent_version_snapshot(agent_version),
            },
            created_by=created_by,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(self, run_id: UUID) -> Run | None:
        run = await self._session.get(Run, run_id)
        if run is not None:
            run.latest_sequence = await self._latest_sequence(run_id)
        return run

    async def list_sop_runs(
        self,
        *,
        sop_id: str,
        env_key: str,
        limit: int = 20,
    ) -> list[Run]:
        statement = (
            select(Run)
            .where(Run.subject_type == "sop")
            .where(Run.subject_id == sop_id)
            .where(Run.env_key == env_key)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_recent_sop_runs(
        self,
        *,
        env_key: str,
        limit: int = 20,
    ) -> list[Run]:
        statement = (
            select(Run)
            .where(Run.subject_type == "sop")
            .where(Run.env_key == env_key)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def mark_running(self, run_id: UUID) -> Run:
        run = await self._require_run(run_id)
        run.status = RunStatus.running.value
        run.started_at = datetime.now(UTC)
        await self._session.flush()
        return run

    async def mark_terminal(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        result_status: str | None = None,
        structured_result: dict[str, Any] | None = None,
        raw_graph_output: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> Run:
        run = await self._require_run(run_id)
        await self._session.refresh(run)
        if run.status not in ACTIVE_STATUSES:
            return run

        run.status = status.value
        run.result_status = result_status
        run.structured_result = structured_result
        run.raw_graph_output = raw_graph_output
        run.error = error
        run.finished_at = datetime.now(UTC)
        run.active_conflict_key = None
        await self._session.flush()
        return run

    async def append_event(
        self,
        run_id: UUID,
        *,
        event_type: str,
        thread_id: str,
        payload: dict[str, Any],
        node: str | None = None,
        checkpoint_id: str | None = None,
        task_id: str | None = None,
    ) -> RunEvent:
        sequence = await self._next_sequence(run_id)
        event = RunEvent(
            run_id=run_id,
            sequence=sequence,
            type=event_type,
            node=node,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_events_after(
        self,
        run_id: UUID,
        *,
        after: int = 0,
        limit: int = 100,
    ) -> list[RunEvent]:
        statement = (
            select(RunEvent)
            .where(RunEvent.run_id == run_id)
            .where(RunEvent.sequence > after)
            .order_by(RunEvent.sequence)
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def interrupt_active_runs_on_startup(self) -> list[Run]:
        statement = select(Run).where(Run.status.in_(ACTIVE_STATUSES))
        runs = list((await self._session.scalars(statement)).all())
        for run in runs:
            run.status = RunStatus.interrupted.value
            run.finished_at = datetime.now(UTC)
            run.active_conflict_key = None
            await self.append_event(
                run.id,
                event_type="custom",
                thread_id=run.thread_id,
                payload={
                    "message": "Service startup interrupted previous run.",
                    "reason": "startup_cleanup",
                },
            )
        await self._session.flush()
        return runs

    async def commit(self) -> None:
        await self._session.commit()

    async def _get_active_run_by_conflict_key(
        self,
        active_conflict_key: str,
    ) -> Run | None:
        statement = (
            select(Run)
            .where(Run.active_conflict_key == active_conflict_key)
            .where(Run.status.in_(ACTIVE_STATUSES))
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def _require_run(self, run_id: UUID) -> Run:
        run = await self.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        return run

    async def _next_sequence(self, run_id: UUID) -> int:
        await self._lock_run(run_id)
        return await self._latest_sequence(run_id) + 1

    async def _latest_sequence(self, run_id: UUID) -> int:
        statement = select(func.coalesce(func.max(RunEvent.sequence), 0)).where(
            RunEvent.run_id == run_id
        )
        latest_sequence = await self._session.scalar(statement)
        return int(latest_sequence or 0)

    async def _lock_run(self, run_id: UUID) -> None:
        statement = select(Run.id).where(Run.id == run_id).with_for_update()
        locked_run_id = await self._session.scalar(statement)
        if locked_run_id is None:
            raise KeyError(run_id)


def _agent_version_snapshot(agent_version: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "id": str(agent_version.id),
        "version_number": agent_version.version_number,
        "model": agent_version.model,
    }
    if hasattr(agent_version, "tool_allowlist"):
        snapshot["tool_allowlist"] = list(agent_version.tool_allowlist)
    if hasattr(agent_version, "mcp_server_ids"):
        snapshot["mcp_server_ids"] = list(agent_version.mcp_server_ids)
    return snapshot

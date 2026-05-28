from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sop_quality_checks import SopQualityCheck, SopQualityEvent

ACTIVE_CHECK_STATUSES = {"pending", "running"}


class ActiveSopQualityCheckExistsError(Exception):
    def __init__(self, active_check_id: UUID) -> None:
        self.active_check_id = active_check_id
        super().__init__(str(active_check_id))


class SopQualityCheckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_check(
        self,
        *,
        sop_id: str,
        env_key: str,
        graph_name: str,
        graph_version: str,
        sop_snapshot: dict[str, Any],
        created_by: str | None = None,
    ) -> SopQualityCheck:
        active = await self.get_active_check(sop_id=sop_id, env_key=env_key)
        if active is not None:
            raise ActiveSopQualityCheckExistsError(active.id)

        check = SopQualityCheck(
            sop_id=sop_id,
            env_key=env_key,
            graph_name=graph_name,
            graph_version=graph_version,
            thread_id=str(uuid4()),
            checkpoint_ns=graph_name,
            status="pending",
            sop_snapshot=sop_snapshot,
            created_by=created_by,
        )
        self._session.add(check)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            active = await self.get_active_check(sop_id=sop_id, env_key=env_key)
            if active is not None:
                raise ActiveSopQualityCheckExistsError(active.id) from exc
            raise
        return check

    async def get_check(self, check_id: UUID) -> SopQualityCheck | None:
        check = await self._session.get(SopQualityCheck, check_id)
        if check is not None:
            check.latest_sequence = await self._latest_sequence(check_id)
        return check

    async def get_active_check(
        self,
        sop_id: str,
        env_key: str,
    ) -> SopQualityCheck | None:
        statement = (
            select(SopQualityCheck)
            .where(SopQualityCheck.sop_id == sop_id)
            .where(SopQualityCheck.env_key == env_key)
            .where(SopQualityCheck.status.in_(ACTIVE_CHECK_STATUSES))
            .limit(1)
        )
        active = await self._session.scalar(statement)
        if active is not None:
            active.latest_sequence = await self._latest_sequence(active.id)
        return active

    async def list_checks(
        self,
        sop_id: str | None = None,
        env_key: str | None = None,
        limit: int = 20,
    ) -> list[SopQualityCheck]:
        statement = select(SopQualityCheck).order_by(SopQualityCheck.created_at.desc())
        if sop_id is not None:
            statement = statement.where(SopQualityCheck.sop_id == sop_id)
        if env_key is not None:
            statement = statement.where(SopQualityCheck.env_key == env_key)
        statement = statement.limit(limit)
        checks = list((await self._session.scalars(statement)).all())
        for check in checks:
            check.latest_sequence = await self._latest_sequence(check.id)
        return checks

    async def mark_running(self, check_id: UUID) -> SopQualityCheck:
        check = await self._require_check(check_id)
        check.status = "running"
        check.started_at = datetime.now(UTC)
        await self._session.flush()
        return check

    async def mark_terminal(
        self,
        check_id: UUID,
        status: str,
        quality_result: str | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> SopQualityCheck:
        check = await self._require_check(check_id)
        await self._session.refresh(check)
        if check.status not in ACTIVE_CHECK_STATUSES:
            return check

        check.status = status
        check.quality_result = quality_result
        check.result = result
        check.error = error
        check.finished_at = datetime.now(UTC)
        await self._session.flush()
        return check

    async def set_current_checkpoint(
        self,
        check_id: UUID,
        checkpoint_id: str,
    ) -> SopQualityCheck:
        check = await self._require_check(check_id)
        check.current_checkpoint_id = checkpoint_id
        await self._session.flush()
        return check

    async def append_event(
        self,
        check_id: UUID,
        event_type: str,
        node: str | None = None,
        checkpoint_id: str | None = None,
        task_id: str | None = None,
        message: str | None = None,
    ) -> SopQualityEvent:
        sequence = await self._next_sequence(check_id)
        event = SopQualityEvent(
            check_id=check_id,
            sequence=sequence,
            type=event_type,
            node=node,
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            message=message,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_events_after(
        self,
        check_id: UUID,
        after: int = 0,
        limit: int = 100,
    ) -> list[SopQualityEvent]:
        statement = (
            select(SopQualityEvent)
            .where(SopQualityEvent.check_id == check_id)
            .where(SopQualityEvent.sequence > after)
            .order_by(SopQualityEvent.sequence)
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def interrupt_active_checks_on_startup(self) -> list[SopQualityCheck]:
        statement = select(SopQualityCheck).where(
            SopQualityCheck.status.in_(ACTIVE_CHECK_STATUSES)
        )
        checks = list((await self._session.scalars(statement)).all())
        for check in checks:
            check.status = "interrupted"
            check.finished_at = datetime.now(UTC)
            await self.append_event(
                check.id,
                event_type="interrupted",
                message="Service startup interrupted previous SOP quality check.",
            )
        await self._session.flush()
        return checks

    async def commit(self) -> None:
        await self._session.commit()

    async def _require_check(self, check_id: UUID) -> SopQualityCheck:
        check = await self.get_check(check_id)
        if check is None:
            raise KeyError(check_id)
        return check

    async def _next_sequence(self, check_id: UUID) -> int:
        await self._lock_check(check_id)
        return await self._latest_sequence(check_id) + 1

    async def _latest_sequence(self, check_id: UUID) -> int:
        statement = select(func.coalesce(func.max(SopQualityEvent.sequence), 0)).where(
            SopQualityEvent.check_id == check_id
        )
        latest_sequence = await self._session.scalar(statement)
        return int(latest_sequence or 0)

    async def _lock_check(self, check_id: UUID) -> None:
        statement = (
            select(SopQualityCheck.id)
            .where(SopQualityCheck.id == check_id)
            .with_for_update()
        )
        locked_check_id = await self._session.scalar(statement)
        if locked_check_id is None:
            raise KeyError(check_id)

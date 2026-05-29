import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.core.config import Settings
from app.repositories.sop_quality_checks import (
    ActiveSopQualityCheckExistsError,
    SopQualityCheckRepository,
)
from app.schemas.sop_quality_checks import SopQualityCheckStatus

SOP_QUALITY_GRAPH_NAME = "sop_quality"
SOP_QUALITY_GRAPH_VERSION = "sop-quality@1"

Scheduler = Callable[[UUID], object]
Committer = Callable[[], object]


class _SessionRepositoryLike(Protocol):
    async def create_session(
        self,
        title: str | None = None,
        thread_id: str | None = None,
    ): ...


@dataclass(frozen=True)
class CheckStartResult:
    check_id: UUID
    status: SopQualityCheckStatus
    created: bool
    status_url: str
    stream_url: str


async def _noop_commit() -> None:
    return None


class SopQualityService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: SopQualityCheckRepository,
        session_repository: _SessionRepositoryLike,
        schedule_check: Scheduler | None = None,
        commit: Committer = _noop_commit,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._session_repository = session_repository
        self._schedule_check = schedule_check
        self._commit = commit

    async def start_check(
        self,
        sop_id: str,
        env_key: str,
        created_by: str | None = None,
    ) -> CheckStartResult:
        self._settings.get_environment(env_key)
        active = await self._repository.get_active_check(sop_id=sop_id, env_key=env_key)
        if active is not None:
            return self._result(
                active.id,
                status=_status_from_check(active),
                created=False,
            )

        runtime_session = await self._session_repository.create_session(
            title=f"SOP quality check: {sop_id}",
        )

        try:
            check = await self._repository.create_check(
                sop_id=sop_id,
                env_key=env_key,
                graph_name=SOP_QUALITY_GRAPH_NAME,
                graph_version=SOP_QUALITY_GRAPH_VERSION,
                sop_snapshot={},
                created_by=created_by,
                session_id=runtime_session.id,
                thread_id=runtime_session.thread_id,
            )
        except ActiveSopQualityCheckExistsError as exc:
            active = await self._repository.get_check(exc.active_check_id)
            status = _status_from_check(active)
            return self._result(exc.active_check_id, status=status, created=False)

        await self._repository.append_event(check.id, event_type="created")
        await self._commit_if_configured()
        await self._schedule_if_configured(check.id)
        return self._result(
            check.id,
            status=SopQualityCheckStatus.pending,
            created=True,
        )

    async def _commit_if_configured(self) -> None:
        result = self._commit()
        if inspect.isawaitable(result):
            await result

    async def _schedule_if_configured(self, check_id: UUID) -> None:
        if self._schedule_check is None:
            return
        result = self._schedule_check(check_id)
        if inspect.isawaitable(result):
            await result

    def _result(
        self,
        check_id: UUID,
        *,
        status: SopQualityCheckStatus,
        created: bool,
    ) -> CheckStartResult:
        return CheckStartResult(
            check_id=check_id,
            status=status,
            created=created,
            status_url=f"/api/sop-quality-checks/{check_id}",
            stream_url=f"/api/sop-quality-checks/{check_id}/stream",
        )


def _status_from_check(check) -> SopQualityCheckStatus:
    if check is None:
        return SopQualityCheckStatus.running
    try:
        return SopQualityCheckStatus(check.status)
    except ValueError:
        return SopQualityCheckStatus.running

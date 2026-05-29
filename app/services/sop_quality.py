import asyncio
import inspect
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.agent.sop_quality.display import (
    display_state_from_graph_values,
    display_state_from_session_messages,
)
from app.core.config import Settings
from app.repositories.sop_quality_checks import (
    ActiveSopQualityCheckExistsError,
    SopQualityCheckRepository,
)
from app.schemas.sop_quality_checks import (
    SopQualityCheckDetail,
    SopQualityCheckEvent,
    SopQualityCheckStatus,
    SopQualityCheckSummary,
)
from app.services.sop_quality_streaming import SopQualityBroadcast

SOP_QUALITY_GRAPH_NAME = "sop_quality"
SOP_QUALITY_GRAPH_VERSION = "sop-quality@1"
TERMINAL_CHECK_STATUSES = {"succeeded", "failed", "cancelled", "interrupted"}
TERMINAL_EVENT_TYPES = {"completed", "failed", "cancelled", "interrupted"}

Scheduler = Callable[[UUID], object]
Committer = Callable[[], object]


class _SessionRepositoryLike(Protocol):
    async def create_session(
        self,
        title: str | None = None,
        thread_id: str | None = None,
    ): ...

    async def get_messages_after(
        self,
        session_id: int,
        after: int = 0,
        limit: int = 100,
    ): ...


@dataclass(frozen=True)
class CheckStartResult:
    check_id: UUID
    status: SopQualityCheckStatus
    created: bool
    status_url: str
    stream_url: str


class SopQualityCheckNotFoundError(KeyError):
    pass


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
        broadcast: SopQualityBroadcast | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._session_repository = session_repository
        self._schedule_check = schedule_check
        self._commit = commit
        self._broadcast = broadcast

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

    async def list_checks(
        self,
        *,
        sop_id: str | None = None,
        env_key: str | None = None,
        limit: int = 20,
    ) -> list[SopQualityCheckSummary]:
        checks = await self._repository.list_checks(
            sop_id=sop_id,
            env_key=env_key,
            limit=limit,
        )
        return [check_to_summary(check) for check in checks]

    async def get_check_detail(self, check_id: UUID) -> SopQualityCheckDetail:
        check = await self._require_check(check_id)
        messages = []
        session_id = getattr(check, "session_id", None)
        if session_id is not None:
            messages = await self._session_repository.get_messages_after(
                session_id,
                after=0,
                limit=500,
            )
        return check_to_detail(check, messages)

    async def get_events(
        self,
        check_id: UUID,
        *,
        after: int = 0,
    ) -> list[SopQualityCheckEvent]:
        await self._require_check(check_id)
        events = await self._repository.get_events_after(check_id, after=after)
        return [SopQualityCheckEvent(**event_to_dict(event)) for event in events]

    async def ensure_check_exists(self, check_id: UUID) -> None:
        await self._require_check(check_id)

    async def stream_events(
        self,
        check_id: UUID,
        *,
        after: int = 0,
        poll_interval_seconds: float = 0.5,
    ) -> AsyncIterator[dict[str, object]]:
        check = await self._require_check(check_id)
        session_id = getattr(check, "session_id", None)
        cursor = after
        message_cursor = after
        broadcast = self._broadcast
        if broadcast is None:
            return

        async with broadcast.subscribe(check_id) as queue:
            while True:
                if session_id is not None:
                    messages = await self._session_repository.get_messages_after(
                        session_id,
                        after=message_cursor,
                    )
                    for message in messages:
                        sequence = int(getattr(message, "sequence", 0))
                        message_cursor = max(message_cursor, sequence)
                        yield message_to_event(message, check_id)

                events = await self._repository.get_events_after(check_id, after=cursor)
                for event in events:
                    cursor = max(cursor, int(event.sequence))
                    event_dict = event_to_dict(event)
                    yield event_dict
                    if event.type in TERMINAL_EVENT_TYPES:
                        return

                if events:
                    continue

                current_check = await self._repository.get_check(check_id)
                if (
                    current_check is None
                    or current_check.status in TERMINAL_CHECK_STATUSES
                ):
                    return
                try:
                    live_event = await asyncio.wait_for(
                        queue.get(),
                        timeout=poll_interval_seconds,
                    )
                except TimeoutError:
                    continue
                yield live_event
                if live_event.get("type") in TERMINAL_EVENT_TYPES:
                    return

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

    async def _require_check(self, check_id: UUID):
        check = await self._repository.get_check(check_id)
        if check is None:
            raise SopQualityCheckNotFoundError(check_id)
        return check

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


def check_to_summary(check) -> SopQualityCheckSummary:
    return SopQualityCheckSummary(
        check_id=check.id,
        sop_id=check.sop_id,
        env_key=check.env_key,
        status=SopQualityCheckStatus(check.status),
        quality_result=check.quality_result,
        latest_sequence=latest_sequence(check),
        created_at=check.created_at,
        started_at=check.started_at,
        finished_at=check.finished_at,
        error_summary=error_summary(check.error),
    )


def check_to_detail(check, messages=None) -> SopQualityCheckDetail:
    summary = check_to_summary(check)
    message_dicts = [message_to_display_dict(m) for m in (messages or [])]
    if message_dicts:
        display_state = display_state_from_session_messages(
            message_dicts,
            latest_sequence=summary.latest_sequence,
            is_running=check.status in {"pending", "running"},
        )
    else:
        values = graph_values_from_check(check)
        display_state = display_state_from_graph_values(
            values,
            latest_sequence=summary.latest_sequence,
            is_running=check.status in {"pending", "running"},
        )
    return SopQualityCheckDetail(
        **summary.model_dump(),
        graph_name=check.graph_name,
        graph_version=check.graph_version,
        thread_id=check.thread_id,
        checkpoint_ns=check.checkpoint_ns,
        current_checkpoint_id=check.current_checkpoint_id,
        result=check.result,
        error=check.error,
        display_state=display_state,
        session_id=getattr(check, "session_id", None),
    )


def event_to_dict(event) -> dict[str, object]:
    return {
        "check_id": event.check_id,
        "sequence": event.sequence,
        "type": event.type,
        "node": getattr(event, "node", None),
        "checkpoint_id": getattr(event, "checkpoint_id", None),
        "task_id": getattr(event, "task_id", None),
        "message": getattr(event, "message", None),
        "created_at": event.created_at,
    }


def message_to_event(message, check_id: UUID) -> dict[str, object]:
    return {
        "check_id": str(check_id),
        "session_id": getattr(message, "session_id", None),
        "sequence": getattr(message, "sequence", None),
        "type": "message",
        "role": getattr(message, "role", None),
        "content": getattr(message, "content", None),
        "additional_kwargs": dict(getattr(message, "additional_kwargs", {}) or {}),
        "created_at": getattr(message, "created_at", None),
    }


def message_to_display_dict(message) -> dict[str, object]:
    return {
        "step": step_from_message(message),
        "role": getattr(message, "role", None),
        "content": getattr(message, "content", None),
        "additional_kwargs": dict(getattr(message, "additional_kwargs", {}) or {}),
    }


def step_from_message(message) -> str | None:
    kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(kwargs, dict):
        step = kwargs.get("step")
        if isinstance(step, str):
            return step
    return None


def graph_values_from_check(check) -> dict[str, object]:
    values: dict[str, object] = {"sop_snapshot": getattr(check, "sop_snapshot", {})}
    if isinstance(check.result, dict):
        values["result"] = check.result
        if isinstance(check.result.get("findings"), list):
            values["findings"] = check.result["findings"]
        if isinstance(check.result.get("quality_result"), str):
            values["quality_result"] = check.result["quality_result"]
        if isinstance(check.result.get("review_output"), str):
            values["review_output"] = check.result["review_output"]
        if isinstance(check.result.get("submission_result"), dict):
            values["submission_result"] = check.result["submission_result"]
    return values


def latest_sequence(check) -> int:
    explicit_sequence = getattr(check, "latest_sequence", None)
    if isinstance(explicit_sequence, int):
        return explicit_sequence
    events = getattr(check, "__dict__", {}).get("events", [])
    if not events:
        return 0
    return max(int(event.sequence) for event in events)


def error_summary(error: object) -> str | None:
    if isinstance(error, dict):
        message = error.get("message")
        return message if isinstance(message, str) else None
    return None

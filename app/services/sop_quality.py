import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from agent.graph import run_mock_sop_quality_graph
from app.core.config import Settings
from app.repositories.runs import ActiveRunExistsError, RunRepository
from app.schemas.runs import RunStatus
from app.services.sop_client import SopClient


@dataclass(frozen=True)
class RunStartResult:
    accepted: bool
    status_url: str
    events_url: str
    run_id: UUID | None = None
    active_run_id: UUID | None = None
    status: RunStatus | None = None
    message: str | None = None


Scheduler = Callable[[UUID], object]
Committer = Callable[[], Awaitable[None]]


async def _noop_commit() -> None:
    return None


class SopQualityService:
    def __init__(
        self,
        *,
        settings: Settings,
        sop_client: SopClient,
        repository: RunRepository,
        schedule_run: Scheduler | None = None,
        commit: Committer = _noop_commit,
    ) -> None:
        self._settings = settings
        self._sop_client = sop_client
        self._repository = repository
        self._schedule_run = schedule_run
        self._commit = commit

    async def start_run(
        self,
        sop_id: str,
        env_key: str,
        created_by: str | None = None,
    ) -> RunStartResult:
        environment = self._settings.get_environment(env_key)
        sop_snapshot = await self._sop_client.get_sop(sop_id, env_key)
        active_conflict_key = f"sop:{sop_id}:env:{env_key}"

        try:
            run = await self._repository.create_sop_run(
                sop_id=sop_id,
                env_key=env_key,
                env_snapshot=environment.public_dict(),
                sop_snapshot=sop_snapshot.model_dump(mode="json"),
                active_conflict_key=active_conflict_key,
                created_by=created_by,
            )
        except ActiveRunExistsError as exc:
            return self._conflict_result(exc.active_run_id)

        await self._commit()
        await self._schedule_if_configured(run.id)
        return RunStartResult(
            accepted=True,
            run_id=run.id,
            status=RunStatus.pending,
            status_url=f"/api/runs/{run.id}",
            events_url=f"/api/runs/{run.id}/events",
        )

    async def _schedule_if_configured(self, run_id: UUID) -> None:
        if self._schedule_run is None:
            return
        result = self._schedule_run(run_id)
        if inspect.isawaitable(result):
            await result

    def _conflict_result(self, active_run_id: UUID) -> RunStartResult:
        return RunStartResult(
            accepted=False,
            active_run_id=active_run_id,
            status=RunStatus.running,
            message="An active run already exists for this SOP and environment.",
            status_url=f"/api/runs/{active_run_id}",
            events_url=f"/api/runs/{active_run_id}/events",
        )


async def run_sop_quality_graph(
    run_id: UUID,
    repository: RunRepository,
) -> dict[str, Any]:
    run = await repository.mark_running(run_id)
    await repository.append_event(
        run_id,
        event_type="custom",
        thread_id=run.thread_id,
        payload={"message": "Started mock SOP quality graph."},
        node="start",
    )
    raw_graph_output = await run_mock_sop_quality_graph(
        run_id=str(run_id),
        sop_snapshot=run.subject_snapshot,
    )
    await repository.append_event(
        run_id,
        event_type="updates",
        thread_id=run.thread_id,
        payload={"status": raw_graph_output["status"]},
        node="validate_sop",
    )
    await repository.mark_terminal(
        run_id,
        RunStatus.success,
        raw_graph_output=raw_graph_output,
        structured_result=None,
        result_status="mock_success",
    )
    return raw_graph_output

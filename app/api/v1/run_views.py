from typing import Any

from app.schemas.runs import RunStatus, RunSummary


def run_to_summary(run: Any) -> RunSummary:
    metadata = run.metadata_
    return RunSummary(
        run_id=run.id,
        subject_type=metadata["subject_type"],
        subject_id=metadata["subject_id"],
        status=RunStatus(run.status),
        current_node=run.current_node,
        completed_nodes=list(run.completed_nodes),
        latest_sequence=_latest_sequence(run),
        started_at=run.started_at,
        finished_at=run.finished_at,
        result_status=run.result_status,
        error_summary=_error_summary(run.error),
    )


def _latest_sequence(run: Any) -> int:
    explicit_sequence = getattr(run, "latest_sequence", None)
    if isinstance(explicit_sequence, int):
        return explicit_sequence

    events = getattr(run, "events", [])
    if not events:
        return 0
    return max(int(event.sequence) for event in events)


def _error_summary(error: object) -> str | None:
    if isinstance(error, dict):
        message = error.get("message")
        return message if isinstance(message, str) else None
    return None

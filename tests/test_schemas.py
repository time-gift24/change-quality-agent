from uuid import uuid4

from app.schemas.runs import RunStatus, RunSummary
from app.schemas.sop import SopSnapshot


def test_run_status_uses_official_values() -> None:
    assert {status.value for status in RunStatus} == {
        "pending",
        "running",
        "success",
        "error",
        "timeout",
        "interrupted",
    }


def test_run_summary_exposes_stable_projection() -> None:
    run_id = uuid4()
    summary = RunSummary(
        run_id=run_id,
        subject_type="sop",
        subject_id="release-checklist",
        status=RunStatus.running,
        current_node="load_sop",
        completed_nodes=[],
        latest_sequence=1,
    )

    assert summary.run_id == run_id
    assert summary.status == RunStatus.running


def test_sop_snapshot_accepts_raw_payload() -> None:
    snapshot = SopSnapshot(
        sop_id="release-checklist",
        env_key="dev",
        source_version="v1",
        updated_at=None,
        payload={"steps": ["review", "deploy"]},
    )

    assert snapshot.payload["steps"] == ["review", "deploy"]

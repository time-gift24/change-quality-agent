from uuid import uuid4

from app.api.v1.run_views import run_to_summary
from app.schemas.runs import RunStatus


class RunWithLazyEvents:
    id = uuid4()
    status = RunStatus.running.value
    current_node = None
    completed_nodes = []
    started_at = None
    finished_at = None
    result_status = None
    error = None
    metadata_ = {
        "subject_type": "sop",
        "subject_id": "release-checklist",
        "env_key": "dev",
    }

    @property
    def events(self):
        raise AssertionError("summary conversion must not lazy-load events")


def test_run_summary_does_not_lazy_load_events() -> None:
    summary = run_to_summary(RunWithLazyEvents())

    assert summary.latest_sequence == 0

from uuid import uuid4

import pytest

from app.schemas.runs import RunStatus
from app.services.sop_quality import run_sop_quality_graph


class FakeRun:
    def __init__(self) -> None:
        self.id = uuid4()
        self.thread_id = "thread-1"
        self.subject_snapshot = {
            "sop_id": "release-checklist",
            "payload": {"steps": [{"id": "prepare"}]},
        }


class FakeRepository:
    def __init__(self, run: FakeRun) -> None:
        self.run = run
        self.marked_running = False
        self.events = []
        self.terminal_status = None
        self.raw_graph_output = None
        self.committed = False

    async def mark_running(self, run_id):
        assert run_id == self.run.id
        self.marked_running = True
        return self.run

    async def append_event(self, run_id, **kwargs):
        assert run_id == self.run.id
        self.events.append(kwargs)
        return kwargs

    async def mark_terminal(self, run_id, status, **kwargs):
        assert run_id == self.run.id
        self.terminal_status = status
        self.raw_graph_output = kwargs["raw_graph_output"]
        return self.run

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_graph_runner_writes_done_event() -> None:
    run = FakeRun()
    repository = FakeRepository(run)

    await run_sop_quality_graph(run.id, repository)

    assert repository.marked_running is True
    assert any(event["event_type"] in {"custom", "updates"} for event in repository.events)
    assert repository.raw_graph_output == {"status": "mock_success"}
    assert repository.terminal_status == RunStatus.success
    assert repository.committed is True

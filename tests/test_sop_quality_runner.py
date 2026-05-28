from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.services.sop_quality_runner import run_sop_quality_check


class FakeCheck:
    def __init__(self) -> None:
        self.id = uuid4()
        self.sop_id = "release-checklist"
        self.env_key = "dev"
        self.thread_id = "thread-1"
        self.checkpoint_ns = "sop_quality"
        self.current_checkpoint_id = None
        self.sop_snapshot = {
            "sop_id": "release-checklist",
            "payload": {"title": "Release"},
        }


class FakeRepository:
    def __init__(self, check: FakeCheck) -> None:
        self.check = check
        self.events: list[dict] = []
        self.terminal = None

    async def get_check(self, check_id):
        return self.check if check_id == self.check.id else None

    async def mark_running(self, check_id):
        self.events.append({"type": "mark_running"})
        return self.check

    async def append_event(self, check_id, **kwargs):
        self.events.append(kwargs)
        return type("Event", (), {"sequence": len(self.events), **kwargs})()

    async def set_current_checkpoint(self, check_id, checkpoint_id):
        self.check.current_checkpoint_id = checkpoint_id
        return self.check

    async def mark_terminal(self, check_id, status, **kwargs):
        self.terminal = {"status": status, **kwargs}
        return self.check

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_runner_marks_success_and_writes_lifecycle_events() -> None:
    check = FakeCheck()
    repository = FakeRepository(check)

    result = await run_sop_quality_check(check.id, repository, checkpointer=None)

    assert result["status"] == "succeeded"
    assert repository.events[1]["event_type"] == "started"
    assert repository.terminal["status"] == "succeeded"
    assert repository.terminal["result"]["quality_result"] in {"pass", "warn"}


@pytest.mark.asyncio
async def test_runner_reads_latest_top_level_checkpoint() -> None:
    check = FakeCheck()
    repository = FakeRepository(check)

    result = await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=InMemorySaver(),
    )

    assert result["status"] == "succeeded"
    assert check.current_checkpoint_id

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
        self.terminal_kwargs = None
        self.committed = False
        self.operations = []

    async def mark_running(self, run_id):
        assert run_id == self.run.id
        self.marked_running = True
        return self.run

    async def append_event(self, run_id, **kwargs):
        assert run_id == self.run.id
        self.events.append(kwargs)
        self.operations.append(f"append_event:{kwargs['event_type']}")
        return kwargs

    async def mark_terminal(self, run_id, status, **kwargs):
        assert run_id == self.run.id
        self.terminal_status = status
        self.terminal_kwargs = kwargs
        self.raw_graph_output = kwargs.get("raw_graph_output")
        self.operations.append(f"mark_terminal:{status.value}")
        return self.run

    async def commit(self) -> None:
        self.committed = True
        self.operations.append("commit")


@pytest.mark.asyncio
async def test_graph_runner_streams_message_before_update_and_done() -> None:
    run = FakeRun()
    repository = FakeRepository(run)

    await run_sop_quality_graph(run.id, repository)

    assert repository.marked_running is True
    assert [event["event_type"] for event in repository.events] == [
        "custom",
        "messages",
        "updates",
        "done",
    ]
    assert repository.events[1]["payload"]["delta"]
    assert repository.operations == [
        "append_event:custom",
        "commit",
        "append_event:messages",
        "commit",
        "append_event:updates",
        "commit",
        "append_event:done",
        "mark_terminal:success",
        "commit",
    ]
    assert repository.raw_graph_output == {"status": "mock_success"}
    assert repository.terminal_status == RunStatus.success
    assert repository.committed is True


@pytest.mark.asyncio
async def test_graph_runner_persists_error_event(monkeypatch) -> None:
    async def fail_stream(*, run_id, sop_snapshot):
        raise ValueError("invalid SOP payload")
        yield

    monkeypatch.setattr("app.services.sop_quality.stream_mock_sop_quality_graph", fail_stream)
    run = FakeRun()
    repository = FakeRepository(run)

    result = await run_sop_quality_graph(run.id, repository)

    assert result["status"] == "error"
    assert repository.terminal_status == RunStatus.error
    assert repository.terminal_kwargs["error"] == {
        "type": "ValueError",
        "message": "invalid SOP payload",
    }
    assert repository.events[-1]["event_type"] == "error"
    assert repository.events[-1]["payload"] == {
        "type": "ValueError",
        "message": "invalid SOP payload",
    }
    assert repository.committed is True


@pytest.mark.asyncio
async def test_graph_runner_marks_error_when_stream_has_no_raw_graph_output(
    monkeypatch,
) -> None:
    async def stream_without_raw_output(*, run_id, sop_snapshot):
        yield {
            "type": "messages",
            "payload": {"delta": "Validating SOP snapshot."},
            "node": "validate_sop",
        }
        yield {
            "type": "updates",
            "payload": {"status": "mock_success"},
            "node": "validate_sop",
        }

    monkeypatch.setattr(
        "app.services.sop_quality.stream_mock_sop_quality_graph",
        stream_without_raw_output,
    )
    run = FakeRun()
    repository = FakeRepository(run)

    result = await run_sop_quality_graph(run.id, repository)

    assert result["status"] == "error"
    assert repository.terminal_status == RunStatus.error
    assert repository.terminal_kwargs["error"] == {
        "type": "RuntimeError",
        "message": "SOP quality stream ended without raw graph output",
    }
    assert [event["event_type"] for event in repository.events] == [
        "custom",
        "messages",
        "updates",
        "error",
    ]

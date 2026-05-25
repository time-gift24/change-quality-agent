from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_run_repository
from app.main import app
from app.schemas.runs import RunStatus


class FakeEvent:
    def __init__(self, sequence: int, event_type: str = "custom") -> None:
        self.sequence = sequence
        self.type = event_type
        self.node = "review"
        self.thread_id = "thread-1"
        self.checkpoint_id = None
        self.task_id = None
        self.payload = {"message": f"event {sequence}"}
        self.created_at = datetime.now(UTC)


class FakeRun:
    def __init__(self) -> None:
        self.id = uuid4()
        self.thread_id = "thread-1"
        self.current_checkpoint_id = "checkpoint-1"
        self.status = RunStatus.running.value
        self.current_node = "review"
        self.completed_nodes = ["load_sop"]
        self.started_at = None
        self.finished_at = None
        self.result_status = None
        self.error = None
        self.raw_graph_output = {"status": "running"}
        self.metadata_ = {
            "subject_type": "sop",
            "subject_id": "release-checklist",
            "env_key": "dev",
        }
        self.events = [FakeEvent(1), FakeEvent(2)]


class FakeRunRepository:
    def __init__(self, run: FakeRun) -> None:
        self.run = run

    async def get_run(self, run_id):
        return self.run if run_id == self.run.id else None

    async def get_events_after(self, run_id, *, after=0, limit=100):
        assert run_id == self.run.id
        return [event for event in self.run.events if event.sequence > after]


@pytest.fixture(autouse=True)
def override_repository():
    run = FakeRun()
    repository = FakeRunRepository(run)
    app.dependency_overrides[get_run_repository] = lambda: repository
    yield run
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_run_returns_summary(override_repository: FakeRun) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/runs/{override_repository.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["subject_type"] == "sop"
    assert body["subject_id"] == "release-checklist"
    assert "env_key" not in body


@pytest.mark.asyncio
async def test_get_run_debug_includes_thread_fields(
    override_repository: FakeRun,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/runs/{override_repository.id}?debug=true")

    assert response.status_code == 200
    debug = response.json()["debug"]
    assert debug["thread_id"] == "thread-1"
    assert debug["current_checkpoint_id"] == "checkpoint-1"


@pytest.mark.asyncio
async def test_events_replay_after_sequence(override_repository: FakeRun) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/runs/{override_repository.id}/events?after=1")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert "event: custom" in response.text
    assert '"sequence": 2' in response.text

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_sop_quality_check_repository
from app.api.v1 import sop_quality_checks as checks_api
from app.main import app


class FakeEvent:
    def __init__(
        self,
        sequence: int,
        check_id,
        event_type: str = "checkpoint",
        message: str | None = None,
    ) -> None:
        self.check_id = check_id
        self.sequence = sequence
        self.type = event_type
        self.node = "review_sop"
        self.checkpoint_id = f"checkpoint-{sequence}"
        self.task_id = None
        self.message = message or f"event {sequence}"
        self.created_at = datetime.now(UTC)


class FakeCheck:
    def __init__(self) -> None:
        self.id = uuid4()
        self.status = "running"


class FakeRepository:
    def __init__(self, check: FakeCheck) -> None:
        self.check = check
        self.events = [
            FakeEvent(1, check.id),
            FakeEvent(2, check.id, "completed", "done"),
        ]

    async def get_check(self, check_id):
        return self.check if check_id == self.check.id else None

    async def get_events_after(self, check_id, *, after=0, limit=100):
        assert check_id == self.check.id
        return [event for event in self.events if event.sequence > after]


class PollingRepository:
    def __init__(self, check: FakeCheck) -> None:
        self.check = check
        self.polls = 0
        self.event = FakeEvent(1, check.id, "completed", "done")

    async def get_check(self, check_id):
        return self.check if check_id == self.check.id else None

    async def get_events_after(self, check_id, *, after=0, limit=100):
        assert check_id == self.check.id
        self.polls += 1
        if self.polls == 1:
            return []
        return [self.event] if self.event.sequence > after else []


@pytest.fixture(autouse=True)
def override_repository():
    check = FakeCheck()
    repository = FakeRepository(check)
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository
    yield check
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_events_replay_after_sequence(override_repository: FakeCheck) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/sop-quality-checks/{override_repository.id}/events?after=1"
        )

    assert response.status_code == 200
    assert response.json()[0]["check_id"] == str(override_repository.id)
    assert response.json()[0]["sequence"] == 2
    assert response.json()[0]["type"] == "completed"
    assert "payload" not in response.json()[0]


@pytest.mark.asyncio
async def test_stream_replays_stored_events(override_repository: FakeCheck) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/sop-quality-checks/{override_repository.id}/stream?after=1"
        )

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert "event: completed" in response.text
    assert f'"check_id": "{override_repository.id}"' in response.text
    assert '"payload"' not in response.text


@pytest.mark.asyncio
async def test_stream_polls_until_terminal_event(monkeypatch) -> None:
    monkeypatch.setattr(checks_api, "SSE_POLL_INTERVAL_SECONDS", 0)
    check = FakeCheck()
    repository = PollingRepository(check)
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/sop-quality-checks/{check.id}/stream?after=0")

    assert response.status_code == 200
    assert repository.polls == 2
    assert "event: completed" in response.text

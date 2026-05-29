from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import (
    get_session_repository,
    get_sop_quality_check_repository,
)
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
        self.session_id = 42


class FakeMessage:
    def __init__(self, sequence, step, content, role="assistant") -> None:
        self.id = uuid4()
        self.session_id = 42
        self.sequence = sequence
        self.role = role
        self.content = content
        self.additional_kwargs = {"step": step, "kind": "step_message"}
        self.created_at = datetime.now(UTC)


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


class FakeSessionRepository:
    def __init__(self) -> None:
        self.messages: list[FakeMessage] = []

    def add_message(self, message: FakeMessage) -> None:
        self.messages.append(message)

    async def get_messages_after(self, session_id, after=0, limit=100):
        return [m for m in self.messages if m.session_id == session_id and m.sequence > after]


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
    session_repository = FakeSessionRepository()
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository
    app.dependency_overrides[get_session_repository] = lambda: session_repository
    yield check, session_repository
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_events_replay_after_sequence(override_repository) -> None:
    check, _ = override_repository
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/sop-quality-checks/{check.id}/events?after=1"
        )

    assert response.status_code == 200
    assert response.json()[0]["check_id"] == str(check.id)
    assert response.json()[0]["sequence"] == 2
    assert response.json()[0]["type"] == "completed"
    assert "payload" not in response.json()[0]


@pytest.mark.asyncio
async def test_stream_replays_stored_events(override_repository) -> None:
    check, _ = override_repository
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/sop-quality-checks/{check.id}/stream?after=1"
        )

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert "event: completed" in response.text
    assert f'"check_id": "{check.id}"' in response.text
    assert '"payload"' not in response.text


@pytest.mark.asyncio
async def test_stream_polls_until_terminal_event(monkeypatch) -> None:
    monkeypatch.setattr(checks_api, "SSE_POLL_INTERVAL_SECONDS", 0)
    check = FakeCheck()
    repository = PollingRepository(check)
    session_repository = FakeSessionRepository()
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository
    app.dependency_overrides[get_session_repository] = lambda: session_repository

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/sop-quality-checks/{check.id}/stream?after=0")

    assert response.status_code == 200
    assert repository.polls == 2
    assert "event: completed" in response.text


@pytest.mark.asyncio
async def test_stream_replays_session_messages_for_check(monkeypatch, override_repository) -> None:
    """Persisted session messages should be replayed in the SOP stream."""
    monkeypatch.setattr(checks_api, "SSE_POLL_INTERVAL_SECONDS", 0)
    check, session_repository = override_repository
    session_repository.add_message(FakeMessage(1, "load_sop", "Loaded SOP X."))
    session_repository.add_message(FakeMessage(2, "review_sop", "Reviewing..."))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/sop-quality-checks/{check.id}/stream?after=0"
        )

    assert response.status_code == 200
    # Persisted session messages emitted as 'message' events
    assert "event: message" in response.text
    assert "Loaded SOP X." in response.text
    assert "Reviewing..." in response.text

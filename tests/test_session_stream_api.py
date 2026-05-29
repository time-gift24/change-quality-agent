from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_session_repository
from app.api.v1 import sessions as sessions_api
from app.main import app


class FakeMessage:
    def __init__(
        self,
        sequence: int,
        session_id: int = 1,
        role: str = "assistant",
        content: str = "",
        additional_kwargs: dict | None = None,
    ) -> None:
        self.id = uuid4()
        self.session_id = session_id
        self.sequence = sequence
        self.role = role
        self.content = content or f"msg {sequence}"
        self.additional_kwargs = additional_kwargs or {}
        self.created_at = datetime.now(UTC)


class FakeSession:
    def __init__(self) -> None:
        self.id = 1
        self.thread_id = "thread-1"
        self.status = "completed"
        self.title = None
        self.latest_sequence = 0
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class FakeRepository:
    def __init__(self, session: FakeSession, messages: list[FakeMessage]) -> None:
        self.session = session
        self.messages = messages
        self.session.latest_sequence = max(
            (m.sequence for m in messages), default=0
        )

    async def get_session(self, session_id: int):
        return self.session if session_id == self.session.id else None

    async def get_messages_after(self, session_id: int, after: int = 0, limit: int = 100):
        return [m for m in self.messages if m.sequence > after][:limit]

    async def latest_sequence(self, session_id: int) -> int:
        return max((m.sequence for m in self.messages), default=0)


@pytest.mark.asyncio
async def test_stream_replays_persisted_messages_after_cursor(monkeypatch) -> None:
    monkeypatch.setattr(sessions_api, "SSE_POLL_INTERVAL_SECONDS", 0)
    session = FakeSession()
    messages = [
        FakeMessage(1, content="first"),
        FakeMessage(2, content="second"),
    ]
    repository = FakeRepository(session, messages)
    app.dependency_overrides[get_session_repository] = lambda: repository
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/sessions/{session.id}/stream?after=1")

        assert response.status_code == 200
        assert "id: 2" in response.text
        assert "event: message" in response.text
        assert '"sequence": 2' in response.text
        assert '"content": "second"' in response.text
        assert '"content": "first"' not in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stream_emits_terminal_event_for_completed_session(monkeypatch) -> None:
    monkeypatch.setattr(sessions_api, "SSE_POLL_INTERVAL_SECONDS", 0)
    session = FakeSession()
    session.status = "completed"
    repository = FakeRepository(session, [])
    app.dependency_overrides[get_session_repository] = lambda: repository
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/sessions/{session.id}/stream?after=0")

        assert response.status_code == 200
        assert "event: completed" in response.text
        assert '"type": "completed"' in response.text
        assert '"session_id": 1' in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stream_returns_404_for_unknown_session(monkeypatch) -> None:
    monkeypatch.setattr(sessions_api, "SSE_POLL_INTERVAL_SECONDS", 0)
    session = FakeSession()
    repository = FakeRepository(session, [])
    app.dependency_overrides[get_session_repository] = lambda: repository
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/sessions/9999/stream?after=0")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_format_session_sse_advances_cursor_for_persisted_message() -> None:
    sse = sessions_api.format_session_sse(
        {
            "type": "message",
            "id": "u",
            "session_id": 1,
            "sequence": 5,
            "role": "assistant",
            "content": "x",
            "additional_kwargs": {},
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    assert "id: 5" in sse
    assert "event: message" in sse
    assert '"session_id": 1' in sse
    assert '"message": {' not in sse


@pytest.mark.asyncio
async def test_format_session_sse_omits_cursor_for_live_delta() -> None:
    sse = sessions_api.format_session_sse(
        {
            "type": "message_delta",
            "session_id": 1,
            "sequence": None,
            "role": "assistant",
            "content": "partial",
            "additional_kwargs": {"step": "review_sop", "channel": "content"},
        }
    )

    assert "id:" not in sse
    assert "event: message_delta" in sse


def test_message_event_sequence_supports_flat_and_nested_events() -> None:
    assert (
        sessions_api.message_event_sequence(
            {"type": "message", "session_id": 1, "sequence": 8}
        )
        == 8
    )
    assert (
        sessions_api.message_event_sequence(
            {"type": "message", "message": {"session_id": 1, "sequence": 9}}
        )
        == 9
    )
    assert (
        sessions_api.message_event_sequence(
            {"type": "message_delta", "session_id": 1, "sequence": 10}
        )
        is None
    )

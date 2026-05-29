from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_session_repository
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
        self.status = "active"
        self.title = None
        self.latest_sequence = 0
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class FakeRepository:
    def __init__(self, session: FakeSession, messages: list[FakeMessage] | None = None) -> None:
        self.session = session
        self.messages = messages or []
        session.latest_sequence = max(
            (m.sequence for m in self.messages), default=0
        )

    async def get_session(self, session_id: int):
        return self.session if session_id == self.session.id else None

    async def get_messages_after(self, session_id: int, after: int = 0, limit: int = 100):
        assert session_id == self.session.id
        return [m for m in self.messages if m.sequence > after][:limit]

    async def latest_sequence(self, session_id: int) -> int:
        if session_id != self.session.id:
            return 0
        return max((m.sequence for m in self.messages), default=0)


@pytest.fixture
def fake_repository():
    session = FakeSession()
    messages = [
        FakeMessage(1, content="hello"),
        FakeMessage(2, content="world"),
    ]
    repository = FakeRepository(session, messages)
    app.dependency_overrides[get_session_repository] = lambda: repository
    yield repository
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_session_returns_detail(fake_repository: FakeRepository) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/sessions/{fake_repository.session.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["thread_id"] == "thread-1"
    assert body["status"] == "active"
    assert body["latest_sequence"] == 2


@pytest.mark.asyncio
async def test_get_session_not_found_returns_404(fake_repository: FakeRepository) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/sessions/9999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_messages_returns_messages_after(fake_repository: FakeRepository) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/sessions/{fake_repository.session.id}/messages?after=1"
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["sequence"] == 2
    assert body[0]["content"] == "world"
    assert body[0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_list_messages_not_found_returns_404(fake_repository: FakeRepository) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/sessions/9999/messages")

    assert response.status_code == 404

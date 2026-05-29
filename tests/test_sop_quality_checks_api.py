from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import (
    get_session,
    get_session_repository,
    get_sop_quality_check_repository,
)
from app.main import app


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeRuntimeSession:
    def __init__(self, session_id: int = 1, thread_id: str = "thread-1") -> None:
        self.id = session_id
        self.thread_id = thread_id


class FakeSessionRepository:
    def __init__(self) -> None:
        self.created: list[FakeRuntimeSession] = []
        self._next_id = 1
        self.messages: list = []

    async def create_session(
        self, title: str | None = None, thread_id: str | None = None
    ) -> FakeRuntimeSession:
        runtime_session = FakeRuntimeSession(
            session_id=self._next_id,
            thread_id=thread_id or f"thread-{self._next_id}",
        )
        self._next_id += 1
        self.created.append(runtime_session)
        return runtime_session

    async def get_messages_after(self, session_id, after=0, limit=100):
        return [m for m in self.messages if getattr(m, "session_id", None) == session_id and getattr(m, "sequence", 0) > after]


class FakeCheck:
    def __init__(self, check_id=None, session_id: int | None = 99) -> None:
        self.id = check_id or uuid4()
        self.sop_id = "release-checklist"
        self.env_key = "dev"
        self.graph_name = "sop_quality"
        self.graph_version = "sop-quality@1"
        self.thread_id = "thread-1"
        self.checkpoint_ns = "sop_quality"
        self.current_checkpoint_id = None
        self.status = "pending"
        self.quality_result = None
        self.result = None
        self.error = None
        self.created_at = datetime.now(UTC)
        self.started_at = None
        self.finished_at = None
        self.latest_sequence = 0
        self.session_id = session_id


class FakeRepository:
    def __init__(self) -> None:
        self.check = FakeCheck()
        self.events = []
        self.last_create_kwargs: dict = {}

    async def create_check(self, **kwargs):
        self.last_create_kwargs = kwargs
        self.check.session_id = kwargs.get("session_id")
        return self.check

    async def get_active_check(self, *, sop_id, env_key):
        return None

    async def get_check(self, check_id):
        return self.check if check_id == self.check.id else None

    async def append_event(self, check_id, **kwargs):
        event = type(
            "Event",
            (),
            {
                "check_id": check_id,
                "sequence": len(self.events) + 1,
                "created_at": datetime.now(UTC),
                **kwargs,
            },
        )()
        self.events.append(event)
        return event

    async def get_events_after(self, check_id, *, after=0, limit=100):
        return [event for event in self.events if event.sequence > after]

    async def list_checks(self, **kwargs):
        return [self.check]


def make_session_override(session: FakeSession):
    async def override_session():
        yield session

    return override_session


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    app.state.scheduled_check_ids = []

    async def fake_executor(check_id):
        app.state.scheduled_check_ids.append(str(check_id))

    app.state.sop_quality_check_executor = fake_executor
    yield
    app.dependency_overrides.clear()
    del app.state.scheduled_check_ids
    del app.state.sop_quality_check_executor


@pytest.mark.asyncio
async def test_start_check_returns_accepted_and_schedules_runner() -> None:
    session = FakeSession()
    repository = FakeRepository()
    session_repository = FakeSessionRepository()
    app.dependency_overrides[get_session] = make_session_override(session)
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository
    app.dependency_overrides[get_session_repository] = lambda: session_repository

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/sop-quality-checks?sop_id=release-checklist&env=dev"
        )

    assert response.status_code == 202
    body = response.json()
    assert body["check_id"] == str(repository.check.id)
    assert body["created"] is True
    assert app.state.scheduled_check_ids == [str(repository.check.id)]
    assert session_repository.created, "session should be created before check"
    assert repository.last_create_kwargs["session_id"] == session_repository.created[0].id


@pytest.mark.asyncio
async def test_get_check_detail_returns_session_id() -> None:
    repository = FakeRepository()
    repository.check.session_id = 42
    session_repository = FakeSessionRepository()
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository
    app.dependency_overrides[get_session_repository] = lambda: session_repository

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/sop-quality-checks/{repository.check.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["check_id"] == str(repository.check.id)
    assert body["session_id"] == 42
    assert "display_state" in body

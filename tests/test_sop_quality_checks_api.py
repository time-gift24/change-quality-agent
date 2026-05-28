from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_session, get_sop_client, get_sop_quality_check_repository
from app.main import app
from app.schemas.sop import SopSnapshot


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeSopClient:
    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="test",
            updated_at=None,
            payload={"id": sop_id, "title": "Release"},
        )


class FakeCheck:
    def __init__(self, check_id=None) -> None:
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


class FakeRepository:
    def __init__(self) -> None:
        self.check = FakeCheck()
        self.events = []

    async def create_check(self, **kwargs):
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
    app.dependency_overrides[get_session] = make_session_override(session)
    app.dependency_overrides[get_sop_client] = FakeSopClient
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository

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


@pytest.mark.asyncio
async def test_get_check_detail_returns_display_state() -> None:
    repository = FakeRepository()
    app.dependency_overrides[get_sop_quality_check_repository] = lambda: repository

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/sop-quality-checks/{repository.check.id}")

    assert response.status_code == 200
    assert response.json()["check_id"] == str(repository.check.id)
    assert "display_state" in response.json()

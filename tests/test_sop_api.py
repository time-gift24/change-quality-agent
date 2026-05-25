from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_run_repository, get_sop_client
from app.core.database import get_session
from app.main import app
from app.repositories.runs import ActiveRunExistsError
from app.schemas.runs import RunStatus
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
            payload={"id": sop_id, "title": f"Mock SOP {sop_id}"},
        )


class FakeRun:
    def __init__(self, run_id=None) -> None:
        self.id = run_id or uuid4()
        self.thread_id = "thread-1"
        self.status = RunStatus.pending.value
        self.current_node = None
        self.completed_nodes = []
        self.started_at = None
        self.finished_at = None
        self.result_status = None
        self.error = None
        self.subject_snapshot = {"sop_id": "release-checklist", "payload": {"steps": []}}
        self.metadata_ = {
            "subject_type": "sop",
            "subject_id": "release-checklist",
            "env_key": "dev",
        }
        self.events = []


class FakeRunRepository:
    def __init__(self, conflict_run_id=None) -> None:
        self.conflict_run_id = conflict_run_id
        self.created = False
        self.history = [FakeRun()]

    async def create_sop_run(self, **kwargs):
        self.created = True
        if self.conflict_run_id is not None:
            raise ActiveRunExistsError(self.conflict_run_id)
        return FakeRun()

    async def list_sop_runs(self, **kwargs):
        return self.history

    async def mark_running(self, run_id):
        return FakeRun(run_id=run_id)

    async def append_event(self, run_id, **kwargs):
        return kwargs

    async def mark_terminal(self, run_id, status, **kwargs):
        return FakeRun(run_id=run_id)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_session_override(session: FakeSession):
    async def override_session():
        yield session

    return override_session


@pytest.mark.asyncio
async def test_list_environments() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sop/environments")

    assert response.status_code == 200
    assert response.json() == [
        {"key": "dev", "name_zh": "开发", "name_en": "Development"}
    ]


@pytest.mark.asyncio
async def test_get_sop_preview_does_not_create_run() -> None:
    repository = FakeRunRepository()
    app.dependency_overrides[get_sop_client] = FakeSopClient
    app.dependency_overrides[get_run_repository] = lambda: repository

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sop/release-checklist?env=dev")

    assert response.status_code == 200
    assert response.json()["sop_id"] == "release-checklist"
    assert repository.created is False


@pytest.mark.asyncio
async def test_start_sop_run_returns_accepted() -> None:
    session = FakeSession()
    app.dependency_overrides[get_sop_client] = FakeSopClient
    app.dependency_overrides[get_session] = make_session_override(session)
    app.dependency_overrides[get_run_repository] = lambda: FakeRunRepository()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/sop/release-checklist/runs?env=dev")

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_start_sop_run_conflict_returns_409() -> None:
    active_run_id = uuid4()
    app.dependency_overrides[get_session] = make_session_override(FakeSession())
    app.dependency_overrides[get_sop_client] = FakeSopClient
    app.dependency_overrides[get_run_repository] = lambda: FakeRunRepository(
        conflict_run_id=active_run_id
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/sop/release-checklist/runs?env=dev")

    assert response.status_code == 409
    assert response.json()["active_run_id"] == str(active_run_id)


@pytest.mark.asyncio
async def test_list_sop_run_history() -> None:
    app.dependency_overrides[get_run_repository] = lambda: FakeRunRepository()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sop/release-checklist/runs?env=dev")

    assert response.status_code == 200
    assert response.json()[0]["subject_type"] == "sop"

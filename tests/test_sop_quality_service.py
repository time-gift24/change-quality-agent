from uuid import UUID, uuid4

import pytest

from app.core.config import EnvironmentConfig, Settings
from app.repositories.sop_quality_checks import ActiveSopQualityCheckExistsError
from app.services.sop_quality import SopQualityService


class FakeRuntimeSession:
    def __init__(self, session_id: int, thread_id: str) -> None:
        self.id = session_id
        self.thread_id = thread_id
        self.status = "active"


class FakeSessionRepository:
    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.created: list[FakeRuntimeSession] = []
        self._next_id = 1

    async def create_session(
        self, title: str | None = None, thread_id: str | None = None
    ) -> FakeRuntimeSession:
        self.order.append("create_session")
        runtime_session = FakeRuntimeSession(
            session_id=self._next_id,
            thread_id=thread_id or f"thread-{self._next_id}",
        )
        self._next_id += 1
        self.created.append(runtime_session)
        return runtime_session


class FakeRepository:
    def __init__(
        self,
        order: list[str],
        active_check_id: UUID | None = None,
    ) -> None:
        self.order = order
        self.active_check_id = active_check_id
        self.created_kwargs: dict = {}
        self.id = uuid4()
        self.status = "pending"

    async def get_active_check(self, *, sop_id: str, env_key: str):
        self.order.append("get_active_check")
        if self.active_check_id is None:
            return None
        active = FakeRepository([])
        active.id = self.active_check_id
        active.status = "running"
        return active

    async def create_check(self, **kwargs):
        self.order.append("create_check")
        self.created_kwargs = kwargs
        if self.active_check_id is not None:
            raise ActiveSopQualityCheckExistsError(self.active_check_id)
        return self

    async def get_check(self, check_id):
        if self.active_check_id == check_id:
            active = FakeRepository([])
            active.id = check_id
            active.status = "running"
            return active
        return None

    async def append_event(self, check_id, **kwargs):
        self.order.append(kwargs["event_type"])
        return None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environments=[
            EnvironmentConfig(
                key="dev",
                name_zh="dev",
                name_en="Development",
            )
        ]
    )


@pytest.mark.asyncio
async def test_start_check_creates_check_without_fetching_sop(
    settings: Settings,
) -> None:
    order: list[str] = []
    service = SopQualityService(
        settings=settings,
        repository=FakeRepository(order),
        session_repository=FakeSessionRepository(order),
    )

    await service.start_check("release-checklist", "dev")

    assert order[:3] == ["get_active_check", "create_session", "create_check"]


@pytest.mark.asyncio
async def test_start_check_returns_existing_active_check(settings: Settings) -> None:
    order: list[str] = []
    active_check_id = uuid4()
    service = SopQualityService(
        settings=settings,
        repository=FakeRepository(order, active_check_id=active_check_id),
        session_repository=FakeSessionRepository(order),
        schedule_check=lambda check_id: order.append(f"schedule:{check_id}"),
        commit=lambda: order.append("commit"),
    )

    result = await service.start_check("release-checklist", "dev")

    assert result.created is False
    assert result.check_id == active_check_id
    assert result.status_url == f"/api/sop-quality-checks/{active_check_id}"
    assert order == ["get_active_check"]


@pytest.mark.asyncio
async def test_start_check_uses_graph_constants_and_writes_created_event(
    settings: Settings,
) -> None:
    order: list[str] = []
    repository = FakeRepository(order)
    session_repository = FakeSessionRepository(order)
    service = SopQualityService(
        settings=settings,
        repository=repository,
        session_repository=session_repository,
    )

    result = await service.start_check("release-checklist", "dev")

    assert result.created is True
    assert repository.created_kwargs["graph_name"] == "sop_quality"
    assert repository.created_kwargs["graph_version"] == "sop-quality@1"
    assert order == [
        "get_active_check",
        "create_session",
        "create_check",
        "created",
    ]
    assert repository.created_kwargs["sop_snapshot"] == {}
    assert repository.created_kwargs["session_id"] == session_repository.created[0].id
    assert repository.created_kwargs["thread_id"] == session_repository.created[0].thread_id


@pytest.mark.asyncio
async def test_start_check_commits_before_scheduling_new_check(
    settings: Settings,
) -> None:
    order: list[str] = []
    repository = FakeRepository(order)
    service = SopQualityService(
        settings=settings,
        repository=repository,
        session_repository=FakeSessionRepository(order),
        schedule_check=lambda check_id: order.append(f"schedule:{check_id}"),
        commit=lambda: order.append("commit"),
    )

    result = await service.start_check("release-checklist", "dev")

    assert order == [
        "get_active_check",
        "create_session",
        "create_check",
        "created",
        "commit",
        f"schedule:{result.check_id}",
    ]


@pytest.mark.asyncio
async def test_start_check_does_not_create_session_when_active_exists(
    settings: Settings,
) -> None:
    order: list[str] = []
    active_check_id = uuid4()
    session_repository = FakeSessionRepository(order)
    service = SopQualityService(
        settings=settings,
        repository=FakeRepository(order, active_check_id=active_check_id),
        session_repository=session_repository,
    )

    await service.start_check("release-checklist", "dev")

    assert session_repository.created == []
    assert "create_session" not in order

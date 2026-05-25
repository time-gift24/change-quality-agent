from uuid import UUID, uuid4

import pytest

from app.core.config import EnvironmentConfig, Settings
from app.repositories.runs import ActiveRunExistsError
from app.schemas.sop import SopSnapshot
from app.services.sop_quality import SopQualityService


class FakeSopClient:
    def __init__(self, order: list[str]) -> None:
        self._order = order

    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        self._order.append("fetch_sop")
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="test",
            updated_at=None,
            payload={"id": sop_id},
        )


class FakeRepository:
    def __init__(
        self,
        order: list[str],
        conflict_run_id: UUID | None = None,
    ) -> None:
        self.order = order
        self.conflict_run_id = conflict_run_id
        self.created_kwargs = {}
        self.id = uuid4()
        self.thread_id = "thread-1"

    async def create_sop_run(self, **kwargs):
        self.order.append("create_run")
        self.created_kwargs = kwargs
        if self.conflict_run_id is not None:
            raise ActiveRunExistsError(self.conflict_run_id)
        return self


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environments=[
            EnvironmentConfig(
                key="dev",
                name_zh="开发",
                name_en="Development",
                sop_client_options={},
            )
        ]
    )


@pytest.mark.asyncio
async def test_start_sop_run_fetches_sop_before_creating_run(
    settings: Settings,
) -> None:
    order: list[str] = []
    service = SopQualityService(
        settings=settings,
        sop_client=FakeSopClient(order),
        repository=FakeRepository(order),
    )

    await service.start_run("release-checklist", "dev")

    assert order == ["fetch_sop", "create_run"]


@pytest.mark.asyncio
async def test_start_sop_run_returns_conflict_for_active_run(
    settings: Settings,
) -> None:
    active_run_id = uuid4()
    service = SopQualityService(
        settings=settings,
        sop_client=FakeSopClient([]),
        repository=FakeRepository([], conflict_run_id=active_run_id),
    )

    result = await service.start_run("release-checklist", "dev")

    assert result.accepted is False
    assert result.active_run_id == active_run_id
    assert result.status_url == f"/api/runs/{active_run_id}"


@pytest.mark.asyncio
async def test_start_sop_run_builds_conflict_key(settings: Settings) -> None:
    repository = FakeRepository([])
    service = SopQualityService(
        settings=settings,
        sop_client=FakeSopClient([]),
        repository=repository,
    )

    await service.start_run("release-checklist", "dev")

    assert (
        repository.created_kwargs["active_conflict_key"]
        == "sop:release-checklist:env:dev"
    )

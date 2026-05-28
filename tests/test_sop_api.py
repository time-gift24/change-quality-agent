from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_run_repository, get_sop_client
from app.main import app
from app.schemas.sop import SopSnapshot


class FakeSopClient:
    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="test",
            updated_at=None,
            payload={"id": sop_id, "title": f"Mock SOP {sop_id}"},
        )


class FakeRunRepository:
    def __init__(self) -> None:
        self.created = False

    async def create_sop_run(self, **kwargs):
        self.created = True


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


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
async def test_sop_run_routes_are_removed() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/sop/release-checklist/runs?env=dev")

    assert response.status_code == 404

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api import deps
from app.core.database import get_session
from app.main import app
from app.repositories.llm_providers import LlmProviderNotFoundError


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeProvider:
    def __init__(
        self,
        *,
        provider_id=None,
        display_name: str = "OpenAI Main",
        provider_type: str = "openai",
        api_key: str | None = "sk-secret",
    ) -> None:
        self.id = provider_id or uuid4()
        self.display_name = display_name
        self.description = "Primary provider"
        self.provider_type = provider_type
        self.base_url = "https://api.openai.com/v1"
        self.api_key = api_key
        self.default_headers = {
            "Authorization": "Bearer secret",
            "X-Tenant": "quality",
        }
        self.default_query = {"token": "secret", "api-version": "2026-01-01"}
        self.enabled = True
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.deleted_at = None


class FakeRepository:
    def __init__(self) -> None:
        provider = FakeProvider()
        self.provider_id = provider.id
        self.providers = {provider.id: provider}
        self.created_values: dict[str, object] | None = None
        self.updated_values: dict[str, object] | None = None
        self.deleted_id = None

    async def list(self):
        return list(self.providers.values())

    async def get_by_id(self, provider_id):
        return self.providers.get(provider_id)

    async def create(self, **values):
        self.created_values = values
        provider = FakeProvider(
            display_name=values["display_name"],
            provider_type=values["provider_type"],
            api_key=values.get("api_key"),
        )
        for field, value in values.items():
            setattr(provider, field, value)
        self.providers[provider.id] = provider
        return provider

    async def update(self, provider_id, **values):
        provider = self.providers.get(provider_id)
        if provider is None:
            raise LlmProviderNotFoundError(provider_id)
        self.updated_values = values
        for field, value in values.items():
            setattr(provider, field, value)
        return provider

    async def soft_delete(self, provider_id):
        provider = self.providers.get(provider_id)
        if provider is None:
            raise LlmProviderNotFoundError(provider_id)
        self.deleted_id = provider_id
        del self.providers[provider_id]
        return provider


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_session_override(session: FakeSession):
    async def override_session():
        yield session

    return override_session


def override_dependencies(repository: FakeRepository, session: FakeSession):
    app.dependency_overrides[get_session] = make_session_override(session)
    get_llm_provider_repository = getattr(deps, "get_llm_provider_repository", None)
    if get_llm_provider_repository is not None:
        app.dependency_overrides[get_llm_provider_repository] = lambda: repository


@pytest.mark.asyncio
async def test_create_provider_persists_and_masks_response() -> None:
    repository = FakeRepository()
    session = FakeSession()
    override_dependencies(repository, session)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/llm-providers",
            json={
                "display_name": "Azure OpenAI",
                "description": "Azure provider",
                "provider_type": "openai",
                "base_url": "https://example.openai.azure.com/openai/v1",
                "api_key": "sk-azure",
                "default_headers": {"X-Tenant": "quality"},
                "default_query": {"api-version": "2026-01-01"},
                "enabled": True,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Azure OpenAI"
    assert body["api_key_configured"] is True
    assert "api_key" not in body
    assert "key" not in body
    assert repository.created_values is not None
    assert repository.created_values["api_key"] == "sk-azure"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_list_providers_returns_masked_summaries() -> None:
    repository = FakeRepository()
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/llm-providers")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["api_key_configured"] is True
    assert "api_key" not in body[0]
    assert "key" not in body[0]
    assert body[0]["default_headers"]["Authorization"] == "********"
    assert body[0]["default_headers"]["X-Tenant"] == "quality"


@pytest.mark.asyncio
async def test_get_provider_returns_404_when_missing() -> None:
    repository = FakeRepository()
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/llm-providers/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_provider_preserves_api_key_when_omitted() -> None:
    repository = FakeRepository()
    session = FakeSession()
    override_dependencies(repository, session)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/v1/llm-providers/{repository.provider_id}",
            json={"display_name": "OpenAI Renamed"},
        )

    assert response.status_code == 200
    assert repository.updated_values == {"display_name": "OpenAI Renamed"}
    assert response.json()["api_key_configured"] is True
    assert session.commits == 1


@pytest.mark.asyncio
async def test_update_provider_clears_api_key_when_null() -> None:
    repository = FakeRepository()
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/v1/llm-providers/{repository.provider_id}",
            json={"api_key": None},
        )

    assert response.status_code == 200
    assert repository.updated_values == {"api_key": None}
    assert response.json()["api_key_configured"] is False


@pytest.mark.asyncio
async def test_update_provider_clears_headers_and_query_when_null() -> None:
    repository = FakeRepository()
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/v1/llm-providers/{repository.provider_id}",
            json={"default_headers": None, "default_query": None},
        )

    assert response.status_code == 200
    assert repository.updated_values == {"default_headers": {}, "default_query": {}}
    assert response.json()["default_headers"] == {}
    assert response.json()["default_query"] == {}


@pytest.mark.asyncio
async def test_delete_provider_soft_deletes() -> None:
    repository = FakeRepository()
    session = FakeSession()
    override_dependencies(repository, session)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.delete(
            f"/api/v1/llm-providers/{repository.provider_id}"
        )
        get_response = await client.get(
            f"/api/v1/llm-providers/{repository.provider_id}"
        )

    assert response.status_code == 204
    assert get_response.status_code == 404
    assert repository.deleted_id == repository.provider_id
    assert session.commits == 1

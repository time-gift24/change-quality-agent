from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api import deps
from app.main import app
from app.repositories.provider_credentials import (
    ProviderCredentialImmutableFieldError,
    ProviderCredentialNameExistsError,
    ProviderCredentialNotFoundError,
)


BASE_TIME = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


class FakeProviderCredential:
    def __init__(
        self,
        *,
        id: UUID | None = None,
        name: str = "OpenAI Global",
        provider: str | None = "openai",
        base_url: str | None = "https://api.openai.com/v1",
        api_key_ciphertext: str = "sk-test123456",
        api_key_hint: str = "sk-...3456",
        model: str | None = "gpt-4.1-mini",
        metadata_: dict[str, object] | None = None,
        is_active: bool = True,
        scope: str = "global",
        owner_user_id: str | None = None,
        credential_type: str = "llm_provider",
        created_by: str | None = "admin-123",
        updated_by: str | None = "admin-123",
    ) -> None:
        self.id = id or uuid4()
        self.name = name
        self.provider = provider
        self.base_url = base_url
        self.api_key_ciphertext = api_key_ciphertext
        self.api_key_hint = api_key_hint
        self.model = model
        self.metadata_ = metadata_ or {}
        self.is_active = is_active
        self.scope = scope
        self.owner_user_id = owner_user_id
        self.credential_type = credential_type
        self.created_by = created_by
        self.updated_by = updated_by
        self.created_at = BASE_TIME
        self.updated_at = BASE_TIME


class FakeProviderCredentialRepository:
    def __init__(
        self,
        *,
        providers: list[FakeProviderCredential] | None = None,
        name_conflict: bool = False,
        immutable_update: str | None = None,
    ) -> None:
        self.providers = {provider.id: provider for provider in providers or []}
        self.name_conflict = name_conflict
        self.immutable_update = immutable_update
        self.created_kwargs: dict[str, object] | None = None
        self.list_global_calls = 0
        self.get_calls: list[UUID] = []
        self.updated_provider_id: UUID | None = None
        self.updated_kwargs: dict[str, object] | None = None
        self.deleted_provider_id: UUID | None = None
        self.deleted_updated_by: str | None = None
        self.commits = 0

    async def create_llm_provider(self, **kwargs):
        self.created_kwargs = kwargs
        if self.name_conflict:
            raise ProviderCredentialNameExistsError
        provider = FakeProviderCredential(**kwargs)
        self.providers[provider.id] = provider
        return provider

    async def list_global_llm_providers(self):
        self.list_global_calls += 1
        return [
            provider
            for provider in self.providers.values()
            if provider.scope == "global" and provider.owner_user_id is None
        ]

    async def get_global_llm_provider(self, provider_id: UUID):
        self.get_calls.append(provider_id)
        provider = self.providers.get(provider_id)
        if provider is None or provider.scope != "global":
            return None
        return provider

    async def update_global_llm_provider(self, provider_id: UUID, **kwargs):
        self.updated_provider_id = provider_id
        self.updated_kwargs = kwargs
        if self.name_conflict:
            raise ProviderCredentialNameExistsError
        if self.immutable_update is not None:
            raise ProviderCredentialImmutableFieldError(self.immutable_update)
        provider = self.providers.get(provider_id)
        if provider is None or provider.scope != "global":
            raise ProviderCredentialNotFoundError(provider_id)
        for key, value in kwargs.items():
            setattr(provider, key, value)
        return provider

    async def soft_delete_global_llm_provider(
        self,
        provider_id: UUID,
        *,
        updated_by: str,
    ):
        self.deleted_provider_id = provider_id
        self.deleted_updated_by = updated_by
        provider = self.providers.get(provider_id)
        if provider is None or provider.scope != "global":
            raise ProviderCredentialNotFoundError(provider_id)
        provider.is_active = False
        provider.updated_by = updated_by
        return provider

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def override_repository(repository: FakeProviderCredentialRepository) -> None:
    app.dependency_overrides[deps.get_provider_credential_repository] = (
        lambda: repository
    )


def admin_headers() -> dict[str, str]:
    return {"x-user-id": "admin-123", "x-user-role": "admin"}


def create_payload() -> dict[str, object]:
    return {
        "name": "OpenAI Global",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test123456",
        "model": "gpt-4.1-mini",
        "metadata": {"region": "us"},
    }


@pytest.mark.asyncio
async def test_admin_list_llm_providers_requires_user_header() -> None:
    override_repository(FakeProviderCredentialRepository())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/admin/llm-providers")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_list_llm_providers_requires_admin_role() -> None:
    override_repository(FakeProviderCredentialRepository())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/admin/llm-providers",
            headers={"x-user-id": "user-123"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_create_llm_provider_creates_global_provider_and_hides_secret() -> None:
    repository = FakeProviderCredentialRepository()
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/admin/llm-providers",
            json=create_payload(),
            headers=admin_headers(),
        )

    assert response.status_code == 201
    assert repository.created_kwargs == {
        "credential_type": "llm_provider",
        "scope": "global",
        "owner_user_id": None,
        "name": "OpenAI Global",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_ciphertext": "sk-test123456",
        "api_key_hint": "sk-...3456",
        "model": "gpt-4.1-mini",
        "metadata_": {"region": "us"},
        "created_by": "admin-123",
        "updated_by": "admin-123",
    }
    assert repository.commits == 1
    body = response.json()
    assert body["api_key_hint"] == "sk-...3456"
    assert body["metadata"] == {"region": "us"}
    assert "api_key" not in body
    assert "api_key_ciphertext" not in body


@pytest.mark.asyncio
async def test_admin_list_llm_providers_returns_global_records_only() -> None:
    global_provider = FakeProviderCredential()
    user_provider = FakeProviderCredential(
        name="User Provider",
        scope="user",
        owner_user_id="user-123",
    )
    repository = FakeProviderCredentialRepository(
        providers=[global_provider, user_provider],
    )
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/admin/llm-providers",
            headers=admin_headers(),
        )

    assert response.status_code == 200
    assert repository.list_global_calls == 1
    body = response.json()
    assert [item["id"] for item in body] == [str(global_provider.id)]
    assert "api_key" not in body[0]
    assert "api_key_ciphertext" not in body[0]


@pytest.mark.asyncio
async def test_admin_get_llm_provider_returns_404_when_missing() -> None:
    provider_id = uuid4()
    repository = FakeProviderCredentialRepository()
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/admin/llm-providers/{provider_id}",
            headers=admin_headers(),
        )

    assert response.status_code == 404
    assert repository.get_calls == [provider_id]


@pytest.mark.asyncio
async def test_admin_patch_llm_provider_maps_duplicate_name_to_409() -> None:
    provider = FakeProviderCredential()
    repository = FakeProviderCredentialRepository(
        providers=[provider],
        name_conflict=True,
    )
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/admin/llm-providers/{provider.id}",
            json={"name": "Duplicate"},
            headers=admin_headers(),
        )

    assert response.status_code == 409
    assert repository.commits == 0


@pytest.mark.asyncio
async def test_admin_patch_llm_provider_maps_immutable_field_error_to_422() -> None:
    provider = FakeProviderCredential()
    repository = FakeProviderCredentialRepository(
        providers=[provider],
        immutable_update="scope",
    )
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/admin/llm-providers/{provider.id}",
            json={"name": "Renamed"},
            headers=admin_headers(),
        )

    assert response.status_code == 422
    assert repository.commits == 0


@pytest.mark.asyncio
async def test_admin_patch_llm_provider_without_api_key_preserves_secret_fields() -> None:
    provider = FakeProviderCredential()
    repository = FakeProviderCredentialRepository(providers=[provider])
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/admin/llm-providers/{provider.id}",
            json={"name": "Renamed", "metadata": {"team": "quality"}},
            headers=admin_headers(),
        )

    assert response.status_code == 200
    assert repository.updated_provider_id == provider.id
    assert repository.updated_kwargs == {
        "name": "Renamed",
        "metadata_": {"team": "quality"},
        "updated_by": "admin-123",
    }
    assert "api_key_ciphertext" not in repository.updated_kwargs
    assert "api_key_hint" not in repository.updated_kwargs
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_admin_patch_llm_provider_with_api_key_updates_secret_fields() -> None:
    provider = FakeProviderCredential()
    repository = FakeProviderCredentialRepository(providers=[provider])
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/admin/llm-providers/{provider.id}",
            json={"api_key": "sk-new654321"},
            headers=admin_headers(),
        )

    assert response.status_code == 200
    assert repository.updated_kwargs == {
        "api_key_ciphertext": "sk-new654321",
        "api_key_hint": "sk-...4321",
        "updated_by": "admin-123",
    }
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_admin_delete_llm_provider_soft_deletes_and_returns_no_content() -> None:
    provider = FakeProviderCredential()
    repository = FakeProviderCredentialRepository(providers=[provider])
    override_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(
            f"/api/admin/llm-providers/{provider.id}",
            headers=admin_headers(),
        )

    assert response.status_code == 204
    assert response.content == b""
    assert repository.deleted_provider_id == provider.id
    assert repository.deleted_updated_by == "admin-123"
    assert repository.commits == 1

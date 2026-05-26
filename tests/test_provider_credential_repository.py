import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.provider_credentials import (
    ProviderCredentialNameExistsError,
    ProviderCredentialNotFoundError,
    ProviderCredentialRepository,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.db,
    pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"),
        reason="set TEST_DATABASE_URL to run repository integration tests",
    ),
]


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


def user_provider_values(
    owner_user_id: str,
    name: str,
    *,
    is_active: bool = True,
) -> dict[str, object]:
    return {
        "scope": "user",
        "owner_user_id": owner_user_id,
        "name": name,
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_ciphertext": f"secret-{owner_user_id}-{name}",
        "api_key_hint": "sk-...1234",
        "model": "gpt-4.1-mini",
        "metadata_": {"purpose": "tests"},
        "is_active": is_active,
        "created_by": owner_user_id,
        "updated_by": owner_user_id,
    }


def global_provider_values(name: str, *, is_active: bool = True) -> dict[str, object]:
    return {
        "scope": "global",
        "owner_user_id": None,
        "name": name,
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_ciphertext": f"secret-global-{name}",
        "api_key_hint": "sk-...9999",
        "model": "gpt-4.1-mini",
        "metadata_": {"purpose": "global-tests"},
        "is_active": is_active,
        "created_by": "admin",
        "updated_by": "admin",
    }


async def test_user_provider_crud_is_scoped_to_owner(session) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal-openai")
    )

    fetched = await repository.get_user_llm_provider(provider.id, "user-1")
    other_user = await repository.get_user_llm_provider(provider.id, "user-2")

    assert fetched is provider
    assert fetched.credential_type == "llm_provider"
    assert other_user is None


async def test_list_user_llm_providers_returns_only_active_records_for_owner(
    session,
) -> None:
    repository = ProviderCredentialRepository(session)
    active = await repository.create_llm_provider(
        **user_provider_values("user-1", "active")
    )
    await repository.create_llm_provider(
        **user_provider_values("user-1", "inactive", is_active=False)
    )
    await repository.create_llm_provider(**user_provider_values("user-2", "other"))
    await repository.create_llm_provider(**global_provider_values("global"))

    providers = await repository.list_user_llm_providers("user-1")

    assert [provider.id for provider in providers] == [active.id]


async def test_list_global_llm_providers_returns_only_active_global_records(
    session,
) -> None:
    repository = ProviderCredentialRepository(session)
    global_provider = await repository.create_llm_provider(
        **global_provider_values("active-global")
    )
    await repository.create_llm_provider(
        **global_provider_values("inactive-global", is_active=False)
    )
    await repository.create_llm_provider(**user_provider_values("user-1", "personal"))

    providers = await repository.list_global_llm_providers()

    assert [provider.id for provider in providers] == [global_provider.id]


async def test_soft_delete_user_llm_provider_hides_record_from_user_reads(
    session,
) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal-openai")
    )

    deleted = await repository.soft_delete_user_llm_provider(
        provider.id,
        "user-1",
        updated_by="user-1",
    )

    assert deleted.is_active is False
    assert deleted.updated_by == "user-1"
    assert await repository.get_user_llm_provider(provider.id, "user-1") is None
    assert await repository.list_user_llm_providers("user-1") == []


async def test_update_user_llm_provider_changes_only_provided_fields(session) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal-openai")
    )

    updated = await repository.update_user_llm_provider(
        provider.id,
        "user-1",
        name="renamed",
        updated_by="editor",
    )

    assert updated.name == "renamed"
    assert updated.provider == "openai"
    assert updated.base_url == "https://api.openai.com/v1"
    assert updated.model == "gpt-4.1-mini"
    assert updated.metadata_ == {"purpose": "tests"}
    assert updated.updated_by == "editor"


async def test_update_user_llm_provider_rejects_wrong_owner(session) -> None:
    repository = ProviderCredentialRepository(session)
    provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal-openai")
    )

    with pytest.raises(ProviderCredentialNotFoundError):
        await repository.update_user_llm_provider(
            provider.id,
            "user-2",
            name="should-not-change",
        )


async def test_global_llm_provider_update_and_soft_delete_are_scoped_to_global(
    session,
) -> None:
    repository = ProviderCredentialRepository(session)
    global_provider = await repository.create_llm_provider(
        **global_provider_values("global-openai")
    )
    user_provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal-openai")
    )

    updated = await repository.update_global_llm_provider(
        global_provider.id,
        model="gpt-4.1",
        updated_by="admin",
    )
    deleted = await repository.soft_delete_global_llm_provider(
        global_provider.id,
        updated_by="admin",
    )

    assert updated.model == "gpt-4.1"
    assert deleted.is_active is False
    assert deleted.updated_by == "admin"
    assert await repository.get_global_llm_provider(global_provider.id) is None
    assert await repository.get_global_llm_provider(user_provider.id) is None


async def test_update_and_delete_raise_not_found_for_missing_scoped_records(
    session,
) -> None:
    repository = ProviderCredentialRepository(session)
    user_provider = await repository.create_llm_provider(
        **user_provider_values("user-1", "personal-openai")
    )

    with pytest.raises(ProviderCredentialNotFoundError):
        await repository.update_global_llm_provider(user_provider.id, name="global")

    with pytest.raises(ProviderCredentialNotFoundError):
        await repository.soft_delete_global_llm_provider(
            user_provider.id,
            updated_by="admin",
        )


async def test_create_llm_provider_maps_duplicate_names(session) -> None:
    repository = ProviderCredentialRepository(session)
    await repository.create_llm_provider(**user_provider_values("user-1", "duplicate"))

    with pytest.raises(ProviderCredentialNameExistsError):
        await repository.create_llm_provider(
            **user_provider_values("user-1", "duplicate")
        )

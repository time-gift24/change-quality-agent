import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.llm_providers import (
    LlmProviderAlreadyExistsError,
    LlmProviderNotFoundError,
    LlmProviderRepository,
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


async def test_create_and_get_provider_by_key(session) -> None:
    repository = LlmProviderRepository(session)

    provider = await repository.create(
        key="openai_main",
        display_name="OpenAI Main",
        description="Primary OpenAI provider",
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        default_headers={"X-Tenant": "quality"},
        default_query={"api-version": "2026-01-01"},
        enabled=True,
    )

    fetched = await repository.get_by_key("openai_main")

    assert fetched is not None
    assert fetched.id == provider.id
    assert fetched.display_name == "OpenAI Main"
    assert fetched.provider_type == "openai"
    assert fetched.base_url == "https://api.openai.com/v1"
    assert fetched.api_key == "sk-test"
    assert fetched.default_headers == {"X-Tenant": "quality"}
    assert fetched.default_query == {"api-version": "2026-01-01"}
    assert fetched.enabled is True


async def test_duplicate_key_is_rejected_even_after_soft_delete(session) -> None:
    repository = LlmProviderRepository(session)
    await repository.create(
        key="openai_main",
        display_name="OpenAI Main",
        provider_type="openai",
    )

    with pytest.raises(LlmProviderAlreadyExistsError, match="openai_main"):
        await repository.create(
            key="openai_main",
            display_name="OpenAI Duplicate",
            provider_type="openai",
        )

    await repository.soft_delete("openai_main")

    with pytest.raises(LlmProviderAlreadyExistsError, match="openai_main"):
        await repository.create(
            key="openai_main",
            display_name="OpenAI Reused",
            provider_type="openai",
        )


async def test_list_excludes_soft_deleted_providers(session) -> None:
    repository = LlmProviderRepository(session)
    await repository.create(key="openai_main", display_name="OpenAI", provider_type="openai")
    await repository.create(
        key="anthropic_main",
        display_name="Anthropic",
        provider_type="anthropic",
        enabled=False,
    )
    await repository.soft_delete("openai_main")

    providers = await repository.list()

    assert [provider.key for provider in providers] == ["anthropic_main"]
    assert providers[0].enabled is False


async def test_get_by_key_returns_disabled_but_not_deleted_provider(session) -> None:
    repository = LlmProviderRepository(session)
    await repository.create(
        key="anthropic_main",
        display_name="Anthropic",
        provider_type="anthropic",
        enabled=False,
    )
    await repository.create(key="openai_main", display_name="OpenAI", provider_type="openai")
    await repository.soft_delete("openai_main")

    disabled = await repository.get_by_key("anthropic_main")
    deleted = await repository.get_by_key("openai_main")

    assert disabled is not None
    assert disabled.enabled is False
    assert deleted is None


async def test_soft_delete_sets_deleted_at(session) -> None:
    repository = LlmProviderRepository(session)
    await repository.create(key="openai_main", display_name="OpenAI", provider_type="openai")

    deleted = await repository.soft_delete("openai_main")

    assert deleted.deleted_at is not None
    assert await repository.get_by_key("openai_main") is None


async def test_soft_delete_missing_provider_raises(session) -> None:
    repository = LlmProviderRepository(session)

    with pytest.raises(LlmProviderNotFoundError, match="missing"):
        await repository.soft_delete("missing")


async def test_update_api_key_preserve_clear_and_replace(session) -> None:
    repository = LlmProviderRepository(session)
    await repository.create(
        key="openai_main",
        display_name="OpenAI",
        provider_type="openai",
        api_key="sk-original",
    )

    preserved = await repository.update("openai_main", display_name="OpenAI Renamed")
    cleared = await repository.update("openai_main", api_key=None)
    replaced = await repository.update("openai_main", api_key="sk-replaced")

    assert preserved.display_name == "OpenAI Renamed"
    assert preserved.api_key == "sk-original"
    assert cleared.api_key is None
    assert replaced.api_key == "sk-replaced"

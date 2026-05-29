import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.llm_providers import (
    LlmProviderNotFoundError,
    LlmProviderRepository,
)
from app.schemas.llm_providers import LlmProviderDetail

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.db,
    pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"),
        reason="set TEST_DATABASE_URL to run repository integration tests",
    ),
]


@pytest_asyncio.fixture
async def session() -> object:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


async def test_create_and_get_provider_by_id(session: object) -> None:
    repository = LlmProviderRepository(session)

    provider = await repository.create(
        display_name="OpenAI Main",
        description="Primary OpenAI provider",
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        default_headers={"X-Tenant": "quality"},
        default_query={"api-version": "2026-01-01"},
        enabled=True,
    )

    fetched = await repository.get_by_id(provider.id)

    assert fetched is not None
    assert fetched.id == provider.id
    assert fetched.display_name == "OpenAI Main"
    assert fetched.provider_type == "openai"
    assert fetched.base_url == "https://api.openai.com/v1"
    assert fetched.api_key == "sk-test"
    assert fetched.default_headers == {"X-Tenant": "quality"}
    assert fetched.default_query == {"api-version": "2026-01-01"}
    assert fetched.enabled is True


async def test_list_excludes_soft_deleted_providers(session: object) -> None:
    repository = LlmProviderRepository(session)
    openai = await repository.create(
        display_name="OpenAI",
        provider_type="openai",
    )
    anthropic = await repository.create(
        display_name="Anthropic",
        provider_type="anthropic",
        enabled=False,
    )
    await repository.soft_delete(openai.id)

    providers = await repository.list()

    assert [provider.id for provider in providers] == [anthropic.id]
    assert providers[0].enabled is False


async def test_get_by_id_returns_disabled_but_not_deleted_provider(
    session: object,
) -> None:
    repository = LlmProviderRepository(session)
    disabled_provider = await repository.create(
        display_name="Anthropic",
        provider_type="anthropic",
        enabled=False,
    )
    deleted_provider = await repository.create(
        display_name="OpenAI",
        provider_type="openai",
    )
    await repository.soft_delete(deleted_provider.id)

    disabled = await repository.get_by_id(disabled_provider.id)
    deleted = await repository.get_by_id(deleted_provider.id)

    assert disabled is not None
    assert disabled.enabled is False
    assert deleted is None


async def test_soft_delete_sets_deleted_at(session: object) -> None:
    repository = LlmProviderRepository(session)
    provider = await repository.create(display_name="OpenAI", provider_type="openai")

    deleted = await repository.soft_delete(provider.id)

    assert deleted.deleted_at is not None
    assert await repository.get_by_id(provider.id) is None


async def test_soft_delete_missing_provider_raises(session: object) -> None:
    repository = LlmProviderRepository(session)
    provider_id = uuid4()

    with pytest.raises(LlmProviderNotFoundError, match=str(provider_id)):
        await repository.soft_delete(provider_id)


async def test_update_api_key_preserve_clear_and_replace(session: object) -> None:
    repository = LlmProviderRepository(session)
    provider = await repository.create(
        display_name="OpenAI",
        provider_type="openai",
        api_key="sk-original",
    )

    preserved = await repository.update(provider.id, display_name="OpenAI Renamed")
    cleared = await repository.update(provider.id, api_key=None)
    replaced = await repository.update(provider.id, api_key="sk-replaced")

    assert preserved.display_name == "OpenAI Renamed"
    assert preserved.api_key == "sk-original"
    assert cleared.api_key is None
    assert replaced.api_key == "sk-replaced"


async def test_update_returns_serializable_provider_after_commit(
    session: object,
) -> None:
    repository = LlmProviderRepository(session)
    provider = await repository.create(
        display_name="OpenAI",
        provider_type="openai",
        api_key="sk-original",
    )

    updated = await repository.update(provider.id, display_name="OpenAI Renamed")
    await session.commit()
    detail = LlmProviderDetail.model_validate(updated)

    assert detail.display_name == "OpenAI Renamed"
    assert detail.api_key_configured is True

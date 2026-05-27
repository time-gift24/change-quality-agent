from sqlalchemy.exc import IntegrityError
import pytest

from app.repositories.llm_providers import (
    LlmProviderAlreadyExistsError,
    LlmProviderRepository,
)


class IntegrityErrorSession:
    def __init__(self) -> None:
        self.added = None
        self.rolled_back = False

    def add(self, provider) -> None:
        self.added = provider

    async def flush(self) -> None:
        raise IntegrityError("insert", {}, Exception("duplicate key"))

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.asyncio
async def test_create_translates_concurrent_duplicate_integrity_error(monkeypatch):
    session = IntegrityErrorSession()
    repository = LlmProviderRepository(session)  # type: ignore[arg-type]

    async def no_existing_provider(key: str):
        return None

    monkeypatch.setattr(
        repository,
        "_get_by_key_including_deleted",
        no_existing_provider,
    )

    with pytest.raises(LlmProviderAlreadyExistsError):
        await repository.create(
            key="openai_main",
            display_name="OpenAI Main",
            provider_type="openai",
        )

    assert session.added is not None
    assert session.rolled_back is True

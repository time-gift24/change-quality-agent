from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_providers import LlmProvider


class LlmProviderAlreadyExistsError(ValueError):
    pass


class LlmProviderNotFoundError(KeyError):
    pass


class LlmProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **values: Any) -> LlmProvider:
        key = values["key"]
        if await self._get_by_key_including_deleted(key) is not None:
            raise LlmProviderAlreadyExistsError(f"LLM provider already exists: {key}")

        provider = LlmProvider(**values)
        self._session.add(provider)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise LlmProviderAlreadyExistsError(
                f"LLM provider already exists: {key}",
            ) from exc
        return provider

    async def list(self) -> list[LlmProvider]:
        statement = (
            select(LlmProvider)
            .where(LlmProvider.deleted_at.is_(None))
            .order_by(LlmProvider.key)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_by_key(self, key: str) -> LlmProvider | None:
        statement = (
            select(LlmProvider)
            .where(LlmProvider.key == key)
            .where(LlmProvider.deleted_at.is_(None))
        )
        return await self._session.scalar(statement)

    async def require_by_key(self, key: str) -> LlmProvider:
        provider = await self.get_by_key(key)
        if provider is None:
            raise LlmProviderNotFoundError(f"LLM provider not found: {key}")
        return provider

    async def update(self, key: str, **values: Any) -> LlmProvider:
        provider = await self.require_by_key(key)
        for field, value in values.items():
            setattr(provider, field, value)
        await self._session.flush()
        return provider

    async def soft_delete(self, key: str) -> LlmProvider:
        provider = await self.require_by_key(key)
        provider.deleted_at = datetime.now(UTC)
        await self._session.flush()
        return provider

    async def _get_by_key_including_deleted(self, key: str) -> LlmProvider | None:
        statement = select(LlmProvider).where(LlmProvider.key == key)
        return await self._session.scalar(statement)

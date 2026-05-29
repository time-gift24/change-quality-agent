from datetime import UTC, datetime
from typing import NotRequired, TypedDict, Unpack
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_providers import LlmProvider


class LlmProviderValues(TypedDict):
    display_name: NotRequired[str]
    description: NotRequired[str | None]
    provider_type: NotRequired[str]
    base_url: NotRequired[str | None]
    api_key: NotRequired[str | None]
    default_headers: NotRequired[dict[str, str]]
    default_query: NotRequired[dict[str, str]]
    models: NotRequired[list[str]]
    enabled: NotRequired[bool]


class LlmProviderNotFoundError(KeyError):
    pass


class LlmProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **values: Unpack[LlmProviderValues]) -> LlmProvider:
        provider = LlmProvider(**values)
        self._session.add(provider)
        await self._session.flush()
        return provider

    async def list(self) -> list[LlmProvider]:
        statement = (
            select(LlmProvider)
            .where(LlmProvider.deleted_at.is_(None))
            .order_by(LlmProvider.created_at.desc(), LlmProvider.id)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_by_id(self, provider_id: UUID) -> LlmProvider | None:
        provider = await self._session.get(LlmProvider, provider_id)
        if provider is None or provider.deleted_at is not None:
            return None
        return provider

    async def require_by_id(self, provider_id: UUID) -> LlmProvider:
        provider = await self.get_by_id(provider_id)
        if provider is None:
            raise LlmProviderNotFoundError(f"LLM provider not found: {provider_id}")
        return provider

    async def update(
        self,
        provider_id: UUID,
        **values: Unpack[LlmProviderValues],
    ) -> LlmProvider:
        provider = await self.require_by_id(provider_id)
        for field, value in values.items():
            setattr(provider, field, value)
        await self._session.flush()
        await self._session.refresh(provider)
        self._session.expunge(provider)
        return provider

    async def soft_delete(self, provider_id: UUID) -> LlmProvider:
        provider = await self.require_by_id(provider_id)
        provider.deleted_at = datetime.now(UTC)
        await self._session.flush()
        return provider

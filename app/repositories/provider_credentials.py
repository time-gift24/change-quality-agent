from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_credentials import ProviderCredential


class ProviderCredentialNameExistsError(Exception):
    pass


class ProviderCredentialNotFoundError(Exception):
    def __init__(self, provider_id: UUID) -> None:
        self.provider_id = provider_id
        super().__init__(str(provider_id))


class ProviderCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_llm_provider(self, **values: Any) -> ProviderCredential:
        provider = ProviderCredential(
            **{
                **values,
                "credential_type": "llm_provider",
            }
        )
        self._session.add(provider)
        await self._flush_mapping_name_conflict()
        return provider

    async def list_user_llm_providers(
        self,
        owner_user_id: str,
    ) -> list[ProviderCredential]:
        statement = (
            self._active_llm_provider_statement()
            .where(ProviderCredential.scope == "user")
            .where(ProviderCredential.owner_user_id == owner_user_id)
            .order_by(ProviderCredential.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_global_llm_providers(self) -> list[ProviderCredential]:
        statement = (
            self._active_llm_provider_statement()
            .where(ProviderCredential.scope == "global")
            .where(ProviderCredential.owner_user_id.is_(None))
            .order_by(ProviderCredential.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_user_llm_provider(
        self,
        provider_id: UUID,
        owner_user_id: str,
    ) -> ProviderCredential | None:
        statement = (
            self._active_llm_provider_statement()
            .where(ProviderCredential.id == provider_id)
            .where(ProviderCredential.scope == "user")
            .where(ProviderCredential.owner_user_id == owner_user_id)
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def get_global_llm_provider(
        self,
        provider_id: UUID,
    ) -> ProviderCredential | None:
        statement = (
            self._active_llm_provider_statement()
            .where(ProviderCredential.id == provider_id)
            .where(ProviderCredential.scope == "global")
            .where(ProviderCredential.owner_user_id.is_(None))
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def update_user_llm_provider(
        self,
        provider_id: UUID,
        owner_user_id: str,
        **values: Any,
    ) -> ProviderCredential:
        provider = await self.get_user_llm_provider(provider_id, owner_user_id)
        if provider is None:
            raise ProviderCredentialNotFoundError(provider_id)
        await self._update_provider(provider, values)
        return provider

    async def update_global_llm_provider(
        self,
        provider_id: UUID,
        **values: Any,
    ) -> ProviderCredential:
        provider = await self.get_global_llm_provider(provider_id)
        if provider is None:
            raise ProviderCredentialNotFoundError(provider_id)
        await self._update_provider(provider, values)
        return provider

    async def soft_delete_user_llm_provider(
        self,
        provider_id: UUID,
        owner_user_id: str,
        *,
        updated_by: str,
    ) -> ProviderCredential:
        provider = await self.get_user_llm_provider(provider_id, owner_user_id)
        if provider is None:
            raise ProviderCredentialNotFoundError(provider_id)
        await self._soft_delete_provider(provider, updated_by=updated_by)
        return provider

    async def soft_delete_global_llm_provider(
        self,
        provider_id: UUID,
        *,
        updated_by: str,
    ) -> ProviderCredential:
        provider = await self.get_global_llm_provider(provider_id)
        if provider is None:
            raise ProviderCredentialNotFoundError(provider_id)
        await self._soft_delete_provider(provider, updated_by=updated_by)
        return provider

    async def commit(self) -> None:
        await self._session.commit()

    def _active_llm_provider_statement(self):
        return (
            select(ProviderCredential)
            .where(ProviderCredential.credential_type == "llm_provider")
            .where(ProviderCredential.is_active.is_(True))
        )

    async def _update_provider(
        self,
        provider: ProviderCredential,
        values: dict[str, Any],
    ) -> None:
        for key, value in values.items():
            setattr(provider, key, value)
        await self._flush_mapping_name_conflict()

    async def _soft_delete_provider(
        self,
        provider: ProviderCredential,
        *,
        updated_by: str,
    ) -> None:
        provider.is_active = False
        provider.updated_by = updated_by
        await self._session.flush()

    async def _flush_mapping_name_conflict(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ProviderCredentialNameExistsError from exc

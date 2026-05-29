import inspect
from collections.abc import Callable
from uuid import UUID

from app.core.llm_connectivity import test_provider_model_connectivity
from app.core.llm_models import LlmProviderRuntimeConfig
from app.repositories.llm_providers import (
    LlmProviderNotFoundError,
    LlmProviderRepository,
)
from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderModelTestRequest,
    LlmProviderModelTestResponse,
    LlmProviderUpdate,
)

Committer = Callable[[], object]
ConnectivityTester = Callable[
    [LlmProviderRuntimeConfig, str],
    object,
]


class LlmProviderModelNotConfiguredError(ValueError):
    pass


class LlmProviderService:
    def __init__(
        self,
        *,
        repository: LlmProviderRepository,
        commit: Committer | None = None,
        connectivity_tester: ConnectivityTester | None = None,
    ) -> None:
        self._repository = repository
        self._commit = commit
        self._connectivity_tester = (
            connectivity_tester or test_provider_model_connectivity
        )

    async def list_providers(self) -> object:
        return await self._repository.list()

    async def create_provider(self, payload: LlmProviderCreate) -> object:
        provider = await self._repository.create(**payload.model_dump(mode="json"))
        await self._commit_if_configured()
        return provider

    async def get_provider(self, provider_id: UUID) -> object:
        provider = await self._repository.get_by_id(provider_id)
        if provider is None:
            raise LlmProviderNotFoundError(provider_id)
        return provider

    async def update_provider(
        self, provider_id: UUID, payload: LlmProviderUpdate
    ) -> object:
        values = _normalize_update_values(
            payload.model_dump(exclude_unset=True, mode="json")
        )
        provider = await self._repository.update(provider_id, **values)
        await self._commit_if_configured()
        return provider

    async def delete_provider(self, provider_id: UUID) -> None:
        await self._repository.soft_delete(provider_id)
        await self._commit_if_configured()

    async def test_model(
        self,
        provider_id: UUID,
        payload: LlmProviderModelTestRequest,
    ) -> LlmProviderModelTestResponse:
        provider = await self.get_provider(provider_id)
        if payload.model not in provider.models:
            raise LlmProviderModelNotConfiguredError(payload.model)

        result = self._connectivity_tester(_runtime_config(provider), payload.model)
        if inspect.isawaitable(result):
            result = await result
        return result

    async def _commit_if_configured(self) -> None:
        if self._commit is None:
            return
        result = self._commit()
        if inspect.isawaitable(result):
            await result


def _normalize_update_values(values: dict[str, object]) -> dict[str, object]:
    for field in ("default_headers", "default_query"):
        if field in values and values[field] is None:
            values[field] = {}
    return values


def _runtime_config(provider: object) -> LlmProviderRuntimeConfig:
    return LlmProviderRuntimeConfig(
        id=provider.id,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        api_key=provider.api_key,
        default_headers=dict(provider.default_headers or {}),
        default_query=dict(provider.default_query or {}),
        enabled=provider.enabled,
    )

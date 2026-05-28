from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.api.deps import LlmProviderRepositoryDep, SessionDep
from app.core.llm_connectivity import test_provider_model_connectivity
from app.core.llm_models import LlmProviderRuntimeConfig
from app.repositories.llm_providers import (
    LlmProviderNotFoundError,
)
from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
    LlmProviderModelTestRequest,
    LlmProviderModelTestResponse,
    LlmProviderSummary,
    LlmProviderUpdate,
)

router = APIRouter(prefix="/api/v1/llm-providers", tags=["llm-providers"])


@router.get("")
async def list_llm_providers(
    repository: LlmProviderRepositoryDep,
) -> list[LlmProviderSummary]:
    providers = await repository.list()
    return [LlmProviderSummary.model_validate(provider) for provider in providers]


@router.post("", response_model=LlmProviderDetail, status_code=status.HTTP_201_CREATED)
async def create_llm_provider(
    payload: LlmProviderCreate,
    session: SessionDep,
    repository: LlmProviderRepositoryDep,
) -> LlmProviderDetail:
    provider = await repository.create(**payload.model_dump(mode="json"))
    await session.commit()
    return LlmProviderDetail.model_validate(provider)


@router.get("/{provider_id}")
async def get_llm_provider(
    provider_id: Annotated[UUID, Path()],
    repository: LlmProviderRepositoryDep,
) -> LlmProviderDetail:
    provider = await repository.get_by_id(provider_id)
    if provider is None:
        raise _not_found()
    return LlmProviderDetail.model_validate(provider)


@router.patch("/{provider_id}")
async def update_llm_provider(
    provider_id: Annotated[UUID, Path()],
    payload: LlmProviderUpdate,
    session: SessionDep,
    repository: LlmProviderRepositoryDep,
) -> LlmProviderDetail:
    values = _normalize_update_values(payload.model_dump(exclude_unset=True, mode="json"))
    try:
        provider = await repository.update(provider_id, **values)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    await session.commit()
    return LlmProviderDetail.model_validate(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_provider(
    provider_id: Annotated[UUID, Path()],
    session: SessionDep,
    repository: LlmProviderRepositoryDep,
) -> Response:
    try:
        await repository.soft_delete(provider_id)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{provider_id}/test")
async def test_llm_provider_model(
    provider_id: Annotated[UUID, Path()],
    payload: LlmProviderModelTestRequest,
    repository: LlmProviderRepositoryDep,
) -> LlmProviderModelTestResponse:
    provider = await repository.get_by_id(provider_id)
    if provider is None:
        raise _not_found()
    if payload.model not in provider.models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model is not configured for this provider.",
        )

    result = await test_provider_model_connectivity(
        _runtime_config(provider),
        payload.model,
    )
    if result.status == "failed":
        return Response(
            content=result.model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    return result


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="LLM provider not found.",
    )


def _normalize_update_values(values: dict[str, object]) -> dict[str, object]:
    for field in ("default_headers", "default_query"):
        if field in values and values[field] is None:
            values[field] = {}
    return values


def _runtime_config(provider) -> LlmProviderRuntimeConfig:
    return LlmProviderRuntimeConfig(
        id=provider.id,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        api_key=provider.api_key,
        default_headers=dict(provider.default_headers or {}),
        default_query=dict(provider.default_query or {}),
        enabled=provider.enabled,
    )

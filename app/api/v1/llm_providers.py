from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.api.deps import LlmProviderServiceDep
from app.services.llm_providers import (
    LlmProviderModelNotConfiguredError,
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
    service: LlmProviderServiceDep,
) -> list[LlmProviderSummary]:
    providers = await service.list_providers()
    return [LlmProviderSummary.model_validate(provider) for provider in providers]


@router.post("", response_model=LlmProviderDetail, status_code=status.HTTP_201_CREATED)
async def create_llm_provider(
    payload: LlmProviderCreate,
    service: LlmProviderServiceDep,
) -> LlmProviderDetail:
    provider = await service.create_provider(payload)
    return LlmProviderDetail.model_validate(provider)


@router.get("/{provider_id}")
async def get_llm_provider(
    provider_id: Annotated[UUID, Path()],
    service: LlmProviderServiceDep,
) -> LlmProviderDetail:
    try:
        provider = await service.get_provider(provider_id)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    return LlmProviderDetail.model_validate(provider)


@router.patch("/{provider_id}")
async def update_llm_provider(
    provider_id: Annotated[UUID, Path()],
    payload: LlmProviderUpdate,
    service: LlmProviderServiceDep,
) -> LlmProviderDetail:
    try:
        provider = await service.update_provider(provider_id, payload)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    return LlmProviderDetail.model_validate(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_provider(
    provider_id: Annotated[UUID, Path()],
    service: LlmProviderServiceDep,
) -> Response:
    try:
        await service.delete_provider(provider_id)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{provider_id}/test")
async def test_llm_provider_model(
    provider_id: Annotated[UUID, Path()],
    payload: LlmProviderModelTestRequest,
    service: LlmProviderServiceDep,
) -> LlmProviderModelTestResponse:
    try:
        result = await service.test_model(provider_id, payload)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    except LlmProviderModelNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model is not configured for this provider.",
        ) from exc
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

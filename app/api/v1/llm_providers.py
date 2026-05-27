from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.api.deps import LlmProviderRepositoryDep, SessionDep
from app.repositories.llm_providers import (
    LlmProviderAlreadyExistsError,
    LlmProviderNotFoundError,
)
from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
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
    try:
        provider = await repository.create(**payload.model_dump(mode="json"))
    except LlmProviderAlreadyExistsError as exc:
        raise _conflict() from exc
    await session.commit()
    return LlmProviderDetail.model_validate(provider)


@router.get("/{provider_key}")
async def get_llm_provider(
    provider_key: Annotated[str, Path()],
    repository: LlmProviderRepositoryDep,
) -> LlmProviderDetail:
    provider = await repository.get_by_key(provider_key)
    if provider is None:
        raise _not_found()
    return LlmProviderDetail.model_validate(provider)


@router.patch("/{provider_key}")
async def update_llm_provider(
    provider_key: Annotated[str, Path()],
    payload: LlmProviderUpdate,
    session: SessionDep,
    repository: LlmProviderRepositoryDep,
) -> LlmProviderDetail:
    values = _normalize_update_values(payload.model_dump(exclude_unset=True, mode="json"))
    try:
        provider = await repository.update(provider_key, **values)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    await session.commit()
    return LlmProviderDetail.model_validate(provider)


@router.delete("/{provider_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_provider(
    provider_key: Annotated[str, Path()],
    session: SessionDep,
    repository: LlmProviderRepositoryDep,
) -> Response:
    try:
        await repository.soft_delete(provider_key)
    except LlmProviderNotFoundError as exc:
        raise _not_found() from exc
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="LLM provider not found.",
    )


def _conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="LLM provider key already exists.",
    )


def _normalize_update_values(values: dict[str, object]) -> dict[str, object]:
    for field in ("default_headers", "default_query"):
        if field in values and values[field] is None:
            values[field] = {}
    return values

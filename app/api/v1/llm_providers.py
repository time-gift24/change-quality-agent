from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.api.deps import CurrentUserDep, ProviderCredentialRepositoryDep
from app.repositories.provider_credentials import (
    ProviderCredentialImmutableFieldError,
    ProviderCredentialNameExistsError,
    ProviderCredentialNotFoundError,
)
from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
    LlmProviderUpdate,
)
from app.services.provider_credentials import prepare_api_key


router = APIRouter(prefix="/api/llm-providers", tags=["llm-providers"])


@router.get("")
async def list_llm_providers(
    current_user: CurrentUserDep,
    repository: ProviderCredentialRepositoryDep,
) -> list[LlmProviderDetail]:
    providers = await repository.list_user_llm_providers(current_user.user_id)
    return [_provider_detail(provider) for provider in providers]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_llm_provider(
    payload: LlmProviderCreate,
    current_user: CurrentUserDep,
    repository: ProviderCredentialRepositoryDep,
) -> LlmProviderDetail:
    prepared_key = prepare_api_key(payload.api_key)
    try:
        provider = await repository.create_llm_provider(
            credential_type="llm_provider",
            scope="user",
            owner_user_id=current_user.user_id,
            name=payload.name,
            provider=payload.provider,
            base_url=payload.base_url,
            api_key_ciphertext=prepared_key.ciphertext,
            api_key_hint=prepared_key.hint,
            model=payload.model,
            metadata_=payload.metadata,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
    except ProviderCredentialNameExistsError as exc:
        raise _name_conflict() from exc
    except ProviderCredentialImmutableFieldError as exc:
        raise _invalid_provider_update(exc) from exc
    await repository.commit()
    return _provider_detail(provider)


@router.get("/{provider_id}")
async def get_llm_provider(
    provider_id: Annotated[UUID, Path()],
    current_user: CurrentUserDep,
    repository: ProviderCredentialRepositoryDep,
) -> LlmProviderDetail:
    provider = await repository.get_user_llm_provider(
        provider_id,
        current_user.user_id,
    )
    if provider is None:
        raise _not_found()
    return _provider_detail(provider)


@router.patch("/{provider_id}")
async def update_llm_provider(
    provider_id: Annotated[UUID, Path()],
    payload: LlmProviderUpdate,
    current_user: CurrentUserDep,
    repository: ProviderCredentialRepositoryDep,
) -> LlmProviderDetail:
    values = payload.model_dump(exclude_unset=True)
    api_key = values.pop("api_key", None)
    if "metadata" in values:
        values["metadata_"] = values.pop("metadata")
    if api_key is not None:
        prepared_key = prepare_api_key(api_key)
        values["api_key_ciphertext"] = prepared_key.ciphertext
        values["api_key_hint"] = prepared_key.hint
    values["updated_by"] = current_user.user_id

    try:
        provider = await repository.update_user_llm_provider(
            provider_id,
            current_user.user_id,
            **values,
        )
    except ProviderCredentialNotFoundError as exc:
        raise _not_found() from exc
    except ProviderCredentialNameExistsError as exc:
        raise _name_conflict() from exc
    except ProviderCredentialImmutableFieldError as exc:
        raise _invalid_provider_update(exc) from exc
    await repository.commit()
    return _provider_detail(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_provider(
    provider_id: Annotated[UUID, Path()],
    current_user: CurrentUserDep,
    repository: ProviderCredentialRepositoryDep,
) -> Response:
    try:
        await repository.soft_delete_user_llm_provider(
            provider_id,
            current_user.user_id,
            updated_by=current_user.user_id,
        )
    except ProviderCredentialNotFoundError as exc:
        raise _not_found() from exc
    await repository.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _provider_detail(provider) -> LlmProviderDetail:
    return LlmProviderDetail(
        id=provider.id,
        name=provider.name,
        provider=provider.provider,
        base_url=provider.base_url,
        api_key_hint=provider.api_key_hint,
        model=provider.model,
        metadata=provider.metadata_,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def _name_conflict() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT)


def _invalid_provider_update(
    exc: ProviderCredentialImmutableFieldError,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
    )

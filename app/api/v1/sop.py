from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SopClientDep
from app.core.config import settings
from app.schemas.sop import EnvironmentPublic, SopSnapshot
from app.services.sop_client import SopClientError, SopNotFoundError

router = APIRouter(prefix="/api/sop", tags=["sop"])


@router.get("/environments")
async def list_environments() -> list[EnvironmentPublic]:
    return [
        EnvironmentPublic(**environment.public_dict())
        for environment in settings.environments
    ]


@router.get("/{sop_id}")
async def get_sop_preview(
    sop_id: str,
    sop_client: SopClientDep,
    env: Annotated[str, Query()],
) -> SopSnapshot:
    _get_environment_or_404(env)
    try:
        return await sop_client.get_sop(sop_id, env)
    except SopNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except SopClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY) from exc


def _get_environment_or_404(env_key: str):
    try:
        return settings.get_environment(env_key)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

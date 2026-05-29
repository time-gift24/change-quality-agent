from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import AuthServiceDep, DevAuthServiceDep
from app.schemas.users import DevLoginRequest, UserPublic
from app.services.auth import (
    AuthRequiredError,
    DevLoginAccountNotFoundError,
    DevLoginDisabledError,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def get_me(request: Request, service: AuthServiceDep) -> UserPublic:
    current_user = getattr(request.state, "current_user", None)
    try:
        return service.current_user_public(current_user)
    except AuthRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from exc


@router.post("/dev-login")
async def dev_login(
    payload: DevLoginRequest,
    response: Response,
    service: DevAuthServiceDep,
) -> UserPublic:
    try:
        user = await service.dev_login(payload.account)
    except DevLoginDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from exc
    except DevLoginAccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    response.set_cookie(
        service.session_cookie_name,
        payload.account,
        httponly=True,
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(service: AuthServiceDep) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(service.session_cookie_name)
    return response

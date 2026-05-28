from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import UserRepositoryDep
from app.core.config import settings
from app.repositories.users import DEV_USERS
from app.schemas.users import DevLoginRequest, UserPublic

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEV_LOGIN_ACCOUNTS = frozenset(user["account"] for user in DEV_USERS)


@router.get("/me")
async def get_me(request: Request) -> UserPublic:
    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user_to_public(current_user)


@router.post("/dev-login")
async def dev_login(
    payload: DevLoginRequest,
    response: Response,
    repository: UserRepositoryDep,
) -> UserPublic:
    if not settings.auth_dev_mode:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if payload.account not in DEV_LOGIN_ACCOUNTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user = await repository.get_by_account(payload.account)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    response.set_cookie(
        settings.auth_session_cookie_name,
        payload.account,
        httponly=True,
    )
    return user_to_public(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(settings.auth_session_cookie_name)
    return response


def user_to_public(user) -> UserPublic:
    return UserPublic(
        id=user.id,
        account=user.account,
        is_admin=user.is_admin,
        meta=user.meta or {},
    )

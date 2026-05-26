from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import HTTPException, Request, Response, status


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: str = "user"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


async def fake_auth_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    user_id = request.headers.get("x-user-id")
    role = request.headers.get("x-user-role") or "user"
    request.state.current_user = (
        CurrentUser(user_id=user_id, role=role) if user_id else None
    )
    return await call_next(request)


async def get_current_user(request: Request) -> CurrentUser:
    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return current_user


async def require_admin_user(request: Request) -> CurrentUser:
    current_user = await get_current_user(request)
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user

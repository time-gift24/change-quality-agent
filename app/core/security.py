from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Request

from app.core.config import settings
from app.core.database import async_session
from app.repositories.users import UserRepository


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    account: str
    is_admin: bool
    meta: dict[str, Any]


AUTH_REQUIRED_DETAIL = "Authentication required."


def is_auth_bypass_path(path: str) -> bool:
    normalized_path = path.rstrip("/") or "/"
    return (
        normalized_path == "/health"
        or normalized_path in {"/docs", "/redoc", "/openapi.json"}
        or normalized_path in {"/api/auth/dev-login", "/api/auth/logout"}
    )


async def resolve_current_user(request: Request) -> CurrentUser | None:
    if not settings.auth_dev_mode:
        return None

    account = request.cookies.get(settings.auth_session_cookie_name)
    if account is None:
        return None

    async with async_session() as session:
        user = await UserRepository(session).get_by_account(account)

    if user is None:
        return None

    return CurrentUser(
        id=user.id,
        account=user.account,
        is_admin=user.is_admin,
        meta=dict(user.meta or {}),
    )

from typing import Annotated

from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.auth import (
    CurrentUser,
    fake_auth_middleware,
    get_current_user,
    require_admin_user,
)
from app.core.config import settings


@pytest.fixture(autouse=True)
def enable_local_fake_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "app_environment", "local")


def create_probe_app() -> FastAPI:
    probe_app = FastAPI()
    probe_app.middleware("http")(fake_auth_middleware)

    @probe_app.get("/state")
    async def read_state(request: Request) -> dict[str, bool | str | None]:
        user = request.state.current_user
        if user is None:
            return {"user_id": None, "role": None, "is_admin": False}
        return {
            "user_id": user.user_id,
            "role": user.role,
            "is_admin": user.is_admin,
        }

    @probe_app.get("/me")
    async def read_current_user(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> dict[str, bool | str]:
        return {
            "user_id": current_user.user_id,
            "role": current_user.role,
            "is_admin": current_user.is_admin,
        }

    @probe_app.get("/admin")
    async def read_admin_user(
        current_user: Annotated[CurrentUser, Depends(require_admin_user)],
    ) -> dict[str, bool | str]:
        return {
            "user_id": current_user.user_id,
            "role": current_user.role,
            "is_admin": current_user.is_admin,
        }

    return probe_app


@pytest.mark.asyncio
async def test_fake_auth_middleware_attaches_current_user_from_headers() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/state",
            headers={"x-user-id": "user-123", "x-user-role": "admin"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-123",
        "role": "admin",
        "is_admin": True,
    }


@pytest.mark.asyncio
async def test_fake_auth_middleware_defaults_role_to_user() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/state", headers={"x-user-id": "user-123"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-123",
        "role": "user",
        "is_admin": False,
    }


@pytest.mark.asyncio
async def test_fake_auth_middleware_ignores_headers_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")

    async with AsyncClient(
        transport=ASGITransport(app=create_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/state",
            headers={"x-user-id": "admin-123", "x-user-role": "admin"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": None,
        "role": None,
        "is_admin": False,
    }


@pytest.mark.asyncio
async def test_get_current_user_returns_401_without_user_id() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


@pytest.mark.asyncio
async def test_require_admin_user_returns_403_when_user_role_is_not_admin() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_probe_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/admin", headers={"x-user-id": "user-123"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required."}

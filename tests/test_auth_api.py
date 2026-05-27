from types import SimpleNamespace
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api import deps
from app.core.config import settings
from app.main import app


class FakeUserRepository:
    def __init__(self) -> None:
        self.users = {
            "common": SimpleNamespace(
                id=uuid4(),
                account="common",
                refresh_token="dev-common-refresh-token",
                is_admin=False,
                meta={"source": "dev"},
            ),
            "admin": SimpleNamespace(
                id=uuid4(),
                account="admin",
                refresh_token="dev-admin-refresh-token",
                is_admin=True,
                meta={"source": "dev"},
            ),
        }

    async def get_by_account(self, account: str):
        return self.users.get(account)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def override_user_repository(repository: FakeUserRepository) -> None:
    get_user_repository = getattr(deps, "get_user_repository", None)
    if get_user_repository is not None:
        app.dependency_overrides[get_user_repository] = lambda: repository


@pytest.mark.asyncio
async def test_dev_login_sets_cookie_when_dev_mode_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_dev_mode", True)
    repository = FakeUserRepository()
    override_user_repository(repository)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/auth/dev-login",
            json={"account": "common"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["account"] == "common"
    assert body["is_admin"] is False
    assert body["meta"] == {"source": "dev"}
    assert "refresh_token" not in body
    assert response.cookies[settings.auth_session_cookie_name] == "common"
    assert "httponly" in response.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_dev_login_rejects_when_dev_mode_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_dev_mode", False)
    override_user_repository(FakeUserRepository())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/auth/dev-login",
            json={"account": "common"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dev_login_rejects_unknown_account(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_dev_mode", True)
    override_user_repository(FakeUserRepository())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/auth/dev-login",
            json={"account": "other"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_me_requires_current_user() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_configured_cookie() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={settings.auth_session_cookie_name: "common"},
    ) as client:
        response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"].lower()
    assert settings.auth_session_cookie_name in set_cookie
    assert "max-age=0" in set_cookie

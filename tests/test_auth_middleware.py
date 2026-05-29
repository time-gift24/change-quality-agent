from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.config import settings
from app.main import app


class FakeSession:
    pass


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakeUserRepository:
    def __init__(self, session: FakeSession, user: object = None) -> None:
        self.session = session
        self.user = user
        self.account = None

    async def get_by_account(self, account: str) -> object:
        self.account = account
        if self.user is not None and self.user.account == account:
            return self.user
        return None


def patch_user_repository(monkeypatch: object, repository: FakeUserRepository) -> None:
    monkeypatch.setattr(
        security,
        "async_session",
        lambda: FakeSessionContext(repository.session),
    )
    monkeypatch.setattr(security, "UserRepository", lambda session: repository)


@pytest.mark.asyncio
async def test_api_request_without_user_returns_401(monkeypatch: object) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_dev_mode", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sop/environments")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_health_bypasses_auth(monkeypatch: object) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/auth/dev-login/"),
        ("post", "/api/auth/logout/"),
    ],
)
async def test_auth_routes_with_trailing_slash_bypass_auth(
    monkeypatch: object,
    method: str,
    path: str,
) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await getattr(client, method)(path)

    assert response.status_code != 401


@pytest.mark.asyncio
async def test_resolve_current_user_loads_dev_cookie_user(monkeypatch: object) -> None:
    user = SimpleNamespace(
        id=uuid4(),
        account="common",
        is_admin=False,
        meta={"source": "test"},
    )
    repository = FakeUserRepository(FakeSession(), user=user)
    patch_user_repository(monkeypatch, repository)

    monkeypatch.setattr(settings, "auth_dev_mode", True)

    current_user = await security.resolve_current_user(
        SimpleNamespace(cookies={settings.auth_session_cookie_name: "common"})
    )

    assert current_user == security.CurrentUser(
        id=user.id,
        account="common",
        is_admin=False,
        meta={"source": "test"},
    )
    assert repository.account == "common"


@pytest.mark.asyncio
async def test_api_request_with_cookie_sets_current_user(monkeypatch: object) -> None:
    user = SimpleNamespace(
        id=uuid4(),
        account="common",
        is_admin=False,
        meta={"source": "test"},
    )
    patch_user_repository(monkeypatch, FakeUserRepository(FakeSession(), user=user))

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_dev_mode", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={settings.auth_session_cookie_name: "common"},
    ) as client:
        response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "account": "common",
        "is_admin": False,
        "meta": {"source": "test"},
    }


@pytest.mark.asyncio
async def test_api_request_with_stale_cookie_clears_cookie(monkeypatch: object) -> None:
    patch_user_repository(monkeypatch, FakeUserRepository(FakeSession()))
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_dev_mode", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={settings.auth_session_cookie_name: "missing"},
    ) as client:
        response = await client.get("/api/sop/environments")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
    set_cookie = response.headers["set-cookie"].lower()
    assert settings.auth_session_cookie_name in set_cookie
    assert "max-age=0" in set_cookie

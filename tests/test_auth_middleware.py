from types import SimpleNamespace
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app import main
from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_api_request_without_user_returns_401(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_dev_mode", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sop/environments")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


@pytest.mark.asyncio
async def test_health_bypasses_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_request_with_user_sets_current_user(monkeypatch) -> None:
    current_user = SimpleNamespace(
        id=uuid4(),
        account="common",
        is_admin=False,
        meta={"source": "test"},
    )

    async def fake_resolve_current_user(request):
        return current_user

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(
        main,
        "resolve_current_user",
        fake_resolve_current_user,
        raising=False,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(current_user.id),
        "account": "common",
        "is_admin": False,
        "meta": {"source": "test"},
    }

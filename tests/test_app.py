import logging
from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def app_routes_snapshot() -> Generator[None, None, None]:
    routes = list(app.router.routes)
    yield
    app.router.routes = routes


@pytest.mark.asyncio
async def test_health_check() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_access_log_records_successful_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.access")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert any(
        "GET /health 200" in record.message and "duration_ms=" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_access_log_can_be_disabled(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "access_log_enabled", False)
    caplog.set_level(logging.INFO, logger="app.access")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert not [record for record in caplog.records if record.name == "app.access"]


@pytest.mark.asyncio
async def test_access_log_records_request_exceptions(
    caplog: pytest.LogCaptureFixture,
    app_routes_snapshot: None,
) -> None:
    @app.get("/__test_error")
    async def test_error() -> None:
        raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger="app.access")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/__test_error")

    assert response.status_code == 500
    assert any(
        "GET /__test_error failed" in record.message
        and "duration_ms=" in record.message
        for record in caplog.records
    )

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_auth_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", False)

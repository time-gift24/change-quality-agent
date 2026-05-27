import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_auth_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy API tests run without auth; auth tests opt in with monkeypatch."""
    monkeypatch.setattr(settings, "auth_enabled", False)

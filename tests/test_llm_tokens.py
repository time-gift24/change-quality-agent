import pytest

from app.core import llm_tokens
from app.core.config import settings


def test_codeagent_token_provider_requires_real_refresh_implementation() -> None:
    provider = llm_tokens.CodeAgentTokenProvider()

    with pytest.raises(NotImplementedError, match="token refresh"):
        provider.get_headers()


def test_get_token_provider_rejects_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "codeagent_token_provider", "vault")

    with pytest.raises(ValueError, match="Unsupported CodeAgent token provider: vault"):
        llm_tokens.get_token_provider()

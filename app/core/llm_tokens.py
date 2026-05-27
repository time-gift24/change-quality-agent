from typing import Protocol

from app.core.config import settings

CODEAGENT_TOKEN_PROVIDER = "codeagent"


class TokenProvider(Protocol):
    def get_headers(self) -> dict[str, str]:
        """Return fresh headers for the next model request."""


class CodeAgentTokenProvider:
    def get_headers(self) -> dict[str, str]:
        raise NotImplementedError("CodeAgent token refresh is not implemented.")


def get_token_provider(provider_key: str | None = None) -> TokenProvider:
    key = provider_key or settings.codeagent_token_provider
    if key == CODEAGENT_TOKEN_PROVIDER:
        return CodeAgentTokenProvider()
    raise ValueError(f"Unsupported CodeAgent token provider: {key}")

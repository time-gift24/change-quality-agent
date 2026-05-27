from typing import Any
from dataclasses import dataclass

import httpx
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek

from app.core.config import settings
from app.core.llm_tokens import TokenProvider, get_token_provider

CODEAGENT_MODEL_PREFIX = "codeagent:"
CODEAGENT_INTERNAL_API_KEY = "internal-header-auth"
_CODEAGENT_PROVIDER_CONFIG_KEYS = frozenset(
    {
        "api_key",
        "api_base",
        "base_url",
        "default_headers",
        "http_client",
        "http_async_client",
    }
)


@dataclass(frozen=True)
class LlmProviderRuntimeConfig:
    key: str
    provider_type: str
    base_url: str | None
    api_key: str | None
    default_headers: dict[str, str]
    default_query: dict[str, str]
    enabled: bool


def create_chat_model(model: str, **model_config: Any) -> BaseChatModel:
    if not model.startswith(CODEAGENT_MODEL_PREFIX):
        return init_chat_model(model, **model_config)

    codeagent_model = model.removeprefix(CODEAGENT_MODEL_PREFIX)
    if not codeagent_model:
        raise ValueError("CodeAgent model name is required after 'codeagent:'.")
    if not settings.codeagent_base_url:
        raise ValueError("CODEAGENT_BASE_URL is required for CodeAgent models.")
    provider_keys = sorted(_CODEAGENT_PROVIDER_CONFIG_KEYS.intersection(model_config))
    if provider_keys:
        joined = ", ".join(provider_keys)
        raise ValueError(
            f"CodeAgent model_config cannot include provider config: {joined}"
        )

    token_provider = get_token_provider()
    http_client, http_async_client = _build_token_refreshing_http_clients(token_provider)
    return ChatDeepSeek(
        model=codeagent_model,
        api_key=CODEAGENT_INTERNAL_API_KEY,
        api_base=settings.codeagent_base_url,
        http_client=http_client,
        http_async_client=http_async_client,
        **model_config,
    )


def create_provider_chat_model(
    model: str,
    provider: LlmProviderRuntimeConfig,
    **model_config: Any,
) -> BaseChatModel:
    provider_config: dict[str, Any] = {
        "model_provider": provider.provider_type,
    }
    if provider.base_url:
        provider_config["base_url"] = provider.base_url
    if provider.api_key:
        provider_config["api_key"] = provider.api_key
    if provider.default_headers:
        provider_config["default_headers"] = provider.default_headers
    if provider.default_query:
        provider_config["default_query"] = provider.default_query

    return init_chat_model(model, **provider_config, **model_config)


def _build_token_refreshing_http_clients(
    token_provider: TokenProvider,
) -> tuple[httpx.Client, httpx.AsyncClient]:
    def add_token_headers(request: httpx.Request) -> None:
        request.headers.update(token_provider.get_headers())

    async def add_token_headers_async(request: httpx.Request) -> None:
        request.headers.update(token_provider.get_headers())

    return (
        httpx.Client(event_hooks={"request": [add_token_headers]}),
        httpx.AsyncClient(event_hooks={"request": [add_token_headers_async]}),
    )

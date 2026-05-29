from dataclasses import dataclass
from types import MethodType
from typing import Any
from uuid import UUID

import httpx
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
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
    id: UUID
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
    provider_config_keys = sorted(
        _CODEAGENT_PROVIDER_CONFIG_KEYS.intersection(model_config)
    )
    if provider_config_keys:
        joined = ", ".join(provider_config_keys)
        raise ValueError(
            f"CodeAgent model_config cannot include provider config: {joined}"
        )

    token_provider = get_token_provider()
    http_client, http_async_client = _build_token_refreshing_http_clients(
        token_provider
    )
    chat_model = ChatDeepSeek(
        model=codeagent_model,
        api_key=CODEAGENT_INTERNAL_API_KEY,
        api_base=settings.codeagent_base_url,
        http_client=http_client,
        http_async_client=http_async_client,
        **model_config,
    )
    return _with_deepseek_reasoning_passthrough(chat_model)


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

    chat_model = init_chat_model(model, **provider_config, **model_config)
    if provider.provider_type == "deepseek":
        return _with_deepseek_reasoning_passthrough(chat_model)
    return chat_model


def _with_deepseek_reasoning_passthrough(
    chat_model: BaseChatModel,
) -> BaseChatModel:
    original_get_request_payload = getattr(chat_model, "_get_request_payload", None)
    if original_get_request_payload is None:
        return chat_model

    def _get_request_payload(
        self: BaseChatModel,
        input_: Any,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = original_get_request_payload(input_, stop=stop, **kwargs)
        _copy_reasoning_content_to_payload(self, input_, payload)
        return payload

    chat_model._get_request_payload = MethodType(_get_request_payload, chat_model)
    return chat_model


def _copy_reasoning_content_to_payload(
    chat_model: BaseChatModel,
    input_: Any,
    payload: dict[str, Any],
) -> None:
    try:
        messages = chat_model._convert_input(input_).to_messages()
    except Exception:
        return

    payload_messages = payload.get("messages")
    if not isinstance(payload_messages, list):
        return

    for source_message, payload_message in zip(
        messages, payload_messages, strict=False
    ):
        if not isinstance(source_message, AIMessage):
            continue
        if not isinstance(payload_message, dict):
            continue
        if payload_message.get("role") != "assistant":
            continue
        reasoning_content = _reasoning_content(source_message)
        if reasoning_content:
            payload_message["reasoning_content"] = reasoning_content


def _reasoning_content(message: AIMessage) -> str | None:
    for key in ("reasoning_content", "reasoning"):
        value = message.additional_kwargs.get(key)
        if isinstance(value, str) and value:
            return value
    return None


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

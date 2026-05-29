from time import perf_counter

from app.core.agent_runtime import to_jsonable
from app.core.json_types import JsonObject, JsonValue
from app.core.llm_model_config import LlmModelParameters, dump_llm_model_parameters
from app.core.llm_models import LlmProviderRuntimeConfig, create_provider_chat_model
from app.schemas.llm_providers import LlmProviderModelTestResponse, REDACTED

TEST_MESSAGES = [{"role": "user", "content": "请简短回复：连通性测试通过。"}]
TEST_MODEL_CONFIG = LlmModelParameters(temperature=0)


async def test_provider_model_connectivity(
    provider: LlmProviderRuntimeConfig,
    model: str,
) -> LlmProviderModelTestResponse:
    started = perf_counter()
    request_trace = _request_trace(provider, model)
    try:
        model_config = dump_llm_model_parameters(TEST_MODEL_CONFIG)
        chat_model = create_provider_chat_model(model, provider, **model_config)
        result = await chat_model.ainvoke(TEST_MESSAGES)
        return LlmProviderModelTestResponse(
            status="ok",
            latency_ms=_elapsed_ms(started),
            message=_message_content(result),
            error=None,
            request=request_trace,
            response=_response_trace(result),
        )
    except Exception as exc:
        return LlmProviderModelTestResponse(
            status="failed",
            latency_ms=_elapsed_ms(started),
            message=None,
            error=_sanitize_error(str(exc), provider),
            request=request_trace,
            response={
                "error_type": type(exc).__name__,
                "raw": _sanitize_value(to_jsonable(exc), provider),
            },
        )


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 2)


def _message_content(value: object) -> str:
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if content is not None:
        return str(content)
    return str(value)


def _request_trace(provider: LlmProviderRuntimeConfig, model: str) -> JsonObject:
    return {
        "model": model,
        "provider_type": provider.provider_type,
        "base_url": provider.base_url,
        "api_key_configured": bool(provider.api_key),
        "default_headers": _sanitize_mapping(provider.default_headers, provider),
        "default_query": _sanitize_mapping(provider.default_query, provider),
        "messages": TEST_MESSAGES,
        "model_config": dump_llm_model_parameters(TEST_MODEL_CONFIG),
    }


def _response_trace(value: object) -> JsonObject:
    raw = to_jsonable(value)
    response: JsonObject = {
        "content": _message_content(value),
        "raw": raw,
    }
    if isinstance(raw, dict):
        for key in ("usage_metadata", "response_metadata", "id", "type", "name"):
            if key in raw:
                response[key] = raw[key]
    return response


def _sanitize_mapping(
    values: dict[str, str],
    provider: LlmProviderRuntimeConfig,
) -> dict[str, str]:
    return {
        key: _sanitize_error(value, provider)
        for key, value in values.items()
    }


def _sanitize_value(value: JsonValue, provider: LlmProviderRuntimeConfig) -> JsonValue:
    if isinstance(value, str):
        return _sanitize_error(value, provider)
    if isinstance(value, list):
        return [_sanitize_value(item, provider) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _sanitize_value(item, provider)
            for key, item in value.items()
        }
    return value


def _sanitize_error(message: str, provider: LlmProviderRuntimeConfig) -> str:
    sanitized = message
    secrets = [provider.api_key or ""]
    secrets.extend(provider.default_headers.values())
    secrets.extend(provider.default_query.values())
    for secret in sorted({item for item in secrets if item}, key=len, reverse=True):
        sanitized = sanitized.replace(secret, REDACTED)
    return sanitized

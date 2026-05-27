import httpx
import pytest

from app.core import llm_models
from app.core.config import settings


def test_create_chat_model_builds_codeagent_with_internal_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeChatDeepSeek:
        def __init__(self, **kwargs) -> None:
            calls.append(dict(kwargs))

    monkeypatch.setattr(settings, "codeagent_base_url", "https://llm.internal/v1")
    monkeypatch.setattr(settings, "codeagent_token_provider", "codeagent")
    monkeypatch.setattr(llm_models, "ChatDeepSeek", FakeChatDeepSeek)

    model = llm_models.create_chat_model(
        "codeagent:codeagent-v4-pro",
        temperature=0,
        reasoning_effort="high",
        model_kwargs={"stream_options": {"include_usage": True}},
    )

    assert isinstance(model, FakeChatDeepSeek)
    assert isinstance(calls[0].pop("http_client"), httpx.Client)
    assert isinstance(calls[0].pop("http_async_client"), httpx.AsyncClient)
    assert calls == [
        {
            "model": "codeagent-v4-pro",
            "api_key": "internal-header-auth",
            "api_base": "https://llm.internal/v1",
            "temperature": 0,
            "reasoning_effort": "high",
            "model_kwargs": {"stream_options": {"include_usage": True}},
        }
    ]


def test_create_chat_model_falls_back_to_langchain_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    configured_model = object()

    def fake_init_chat_model(model: str, **model_config):
        calls.append((model, dict(model_config)))
        return configured_model

    monkeypatch.setattr(llm_models, "init_chat_model", fake_init_chat_model)

    model = llm_models.create_chat_model("openai:gpt-5-mini", temperature=0.2)

    assert model is configured_model
    assert calls == [("openai:gpt-5-mini", {"temperature": 0.2})]


def test_create_chat_model_sets_codeagent_api_base_on_real_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "codeagent_base_url", "https://llm.internal/v1")
    monkeypatch.setattr(settings, "codeagent_token_provider", "codeagent")

    model = llm_models.create_chat_model("codeagent:codeagent-v4-pro")

    assert str(model.root_client.base_url) == "https://llm.internal/v1/"


@pytest.mark.asyncio
async def test_codeagent_http_clients_refresh_token_per_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokens = iter(["first-token", "second-token"])

    class RotatingProvider:
        def get_headers(self):
            return {"X-Open-CodeAgent-Token": next(tokens)}

    http_client, http_async_client = llm_models._build_token_refreshing_http_clients(
        RotatingProvider()
    )
    request = httpx.Request("POST", "https://llm.internal/v1/chat/completions")
    http_client.event_hooks["request"][0](request)
    assert request.headers["X-Open-CodeAgent-Token"] == "first-token"

    async_request = httpx.Request("POST", "https://llm.internal/v1/chat/completions")
    await http_async_client.event_hooks["request"][0](async_request)
    assert async_request.headers["X-Open-CodeAgent-Token"] == "second-token"

    http_client.close()
    await http_async_client.aclose()


def test_create_chat_model_requires_codeagent_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "codeagent_base_url", None)

    with pytest.raises(ValueError, match="CODEAGENT_BASE_URL"):
        llm_models.create_chat_model("codeagent:codeagent-v4-pro")


def test_create_chat_model_requires_codeagent_refresh_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "codeagent_base_url", "https://llm.internal/v1")
    monkeypatch.setattr(settings, "codeagent_token_provider", "codeagent")

    model = llm_models.create_chat_model("codeagent:codeagent-v4-pro")
    request = httpx.Request("POST", "https://llm.internal/v1/chat/completions")

    with pytest.raises(NotImplementedError, match="token refresh"):
        model.root_client._client.event_hooks["request"][0](request)


@pytest.mark.parametrize(
    "provider_key",
    [
        "api_key",
        "api_base",
        "base_url",
        "default_headers",
        "http_client",
        "http_async_client",
    ],
)
def test_create_chat_model_rejects_codeagent_provider_config_in_model_config(
    monkeypatch: pytest.MonkeyPatch,
    provider_key: str,
) -> None:
    monkeypatch.setattr(settings, "codeagent_base_url", "https://llm.internal/v1")

    with pytest.raises(ValueError, match="provider config"):
        llm_models.create_chat_model(
            "codeagent:codeagent-v4-pro",
            **{provider_key: "x"},
        )

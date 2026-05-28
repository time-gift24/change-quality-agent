from uuid import uuid4

import pytest

from app.core.create_agent_by_llm_provider import LlmProviderAgentConfigurationError
from app.core.create_deepagents_by_llm_provider import (
    create_deepagents_by_llm_provider,
)
from app.core.llm_models import LlmProviderRuntimeConfig


class FakeProvider:
    def __init__(self, *, models: list[str] | None = None) -> None:
        self.id = uuid4()
        self.provider_type = "deepseek"
        self.base_url = "https://llm.example.test/v1"
        self.api_key = "sk-test"
        self.default_headers = {"X-Tenant": "quality"}
        self.default_query = {"trace": "1"}
        self.enabled = True
        self.models = models if models is not None else ["deepseek-v4-pro"]


class FakeRepository:
    def __init__(self, providers: list[FakeProvider]) -> None:
        self.providers = providers

    async def list(self) -> list[FakeProvider]:
        return self.providers


@pytest.mark.asyncio
async def test_create_deepagents_by_llm_provider_uses_first_provider_and_model() -> None:
    first_provider = FakeProvider(models=["deepseek-v4-pro", "deepseek-chat"])
    repository = FakeRepository([first_provider, FakeProvider(models=["gpt-5-mini"])])
    created_agent = object()
    configured_model = object()
    provider_model_calls: list[tuple[str, LlmProviderRuntimeConfig, dict]] = []
    create_deep_agent_calls: list[dict] = []
    tools = [lambda: "tool"]

    def fake_provider_model_factory(model: str, provider, **model_config):
        provider_model_calls.append((model, provider, dict(model_config)))
        return configured_model

    def fake_create_deep_agent(*, model, tools, system_prompt):
        create_deep_agent_calls.append(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
            }
        )
        return created_agent

    agent = await create_deepagents_by_llm_provider(
        repository,
        system_prompt="Review the SOP carefully.",
        tools=tools,
        model_config={"temperature": 0},
        provider_model_factory=fake_provider_model_factory,
        create_deep_agent=fake_create_deep_agent,
    )

    assert agent is created_agent
    assert provider_model_calls[0][0] == "deepseek-v4-pro"
    assert provider_model_calls[0][1] == LlmProviderRuntimeConfig(
        id=first_provider.id,
        provider_type="deepseek",
        base_url="https://llm.example.test/v1",
        api_key="sk-test",
        default_headers={"X-Tenant": "quality"},
        default_query={"trace": "1"},
        enabled=True,
    )
    assert provider_model_calls[0][2] == {"temperature": 0}
    assert create_deep_agent_calls == [
        {
            "model": configured_model,
            "tools": tools,
            "system_prompt": "Review the SOP carefully.",
        }
    ]


@pytest.mark.asyncio
async def test_create_deepagents_by_llm_provider_fails_without_provider() -> None:
    with pytest.raises(LlmProviderAgentConfigurationError, match="No LLM provider"):
        await create_deepagents_by_llm_provider(FakeRepository([]))


@pytest.mark.asyncio
async def test_create_deepagents_by_llm_provider_fails_without_provider_model() -> None:
    provider = FakeProvider(models=[])

    with pytest.raises(LlmProviderAgentConfigurationError, match="does not list models"):
        await create_deepagents_by_llm_provider(FakeRepository([provider]))

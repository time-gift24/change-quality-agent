from uuid import uuid4

import pytest

from app.agent.manager.agent_factory import (
    AgentFactory,
    LlmProviderAgentConfigurationError,
)
from app.core.llm_models import LlmProviderRuntimeConfig


class FakeProvider:
    def __init__(
        self,
        *,
        models: list[str] | None = None,
        enabled: bool = True,
    ) -> None:
        self.id = uuid4()
        self.provider_type = "deepseek"
        self.base_url = "https://llm.example.test/v1"
        self.api_key = "sk-test"
        self.default_headers = {"X-Tenant": "quality"}
        self.default_query = {"trace": "1"}
        self.enabled = enabled
        self.models = models if models is not None else ["deepseek-v4-pro"]


class FakeRepository:
    def __init__(self, providers: list[FakeProvider]) -> None:
        self.providers = providers

    async def list(self) -> list[FakeProvider]:
        return self.providers


def _assert_provider_model_call(
    call: tuple[str, LlmProviderRuntimeConfig, dict],
    first_provider: FakeProvider,
) -> None:
    model, provider_config, model_config = call
    assert model == "deepseek-v4-pro"
    assert provider_config == LlmProviderRuntimeConfig(
        id=first_provider.id,
        provider_type="deepseek",
        base_url="https://llm.example.test/v1",
        api_key="sk-test",
        default_headers={"X-Tenant": "quality"},
        default_query={"trace": "1"},
        enabled=True,
    )
    assert model_config == {"temperature": 0}


@pytest.mark.asyncio
async def test_agent_factory_create_agent_uses_first_provider_and_model() -> None:
    first_provider = FakeProvider(models=["deepseek-v4-pro", "deepseek-chat"])
    repository = FakeRepository([first_provider, FakeProvider(models=["gpt-5-mini"])])
    created_agent = object()
    configured_model = object()
    provider_model_calls: list[tuple[str, LlmProviderRuntimeConfig, dict]] = []
    create_agent_calls: list[dict] = []
    tools = [lambda: "tool"]

    def fake_provider_model_factory(
        model: str, provider: object, **model_config: object
    ) -> object:
        provider_model_calls.append((model, provider, dict(model_config)))
        return configured_model

    def fake_create_agent(
        *, model: object, tools: object, system_prompt: object
    ) -> object:
        create_agent_calls.append(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
            }
        )
        return created_agent

    factory = AgentFactory(
        repository,
        provider_model_factory=fake_provider_model_factory,
        create_agent_factory=fake_create_agent,
    )

    agent = await factory.create_agent(
        system_prompt="Review the SOP carefully.",
        tools=tools,
        model_config={"temperature": 0},
    )

    assert agent is created_agent
    _assert_provider_model_call(provider_model_calls[0], first_provider)
    assert create_agent_calls == [
        {
            "model": configured_model,
            "tools": tools,
            "system_prompt": "Review the SOP carefully.",
        }
    ]


@pytest.mark.asyncio
async def test_agent_factory_skips_disabled_providers() -> None:
    disabled_provider = FakeProvider(
        models=["disabled-model"],
        enabled=False,
    )
    enabled_provider = FakeProvider(models=["deepseek-v4-pro"])
    repository = FakeRepository([disabled_provider, enabled_provider])
    provider_model_calls: list[tuple[str, LlmProviderRuntimeConfig, dict]] = []

    def fake_provider_model_factory(
        model: str, provider: object, **model_config: object
    ) -> object:
        provider_model_calls.append((model, provider, dict(model_config)))
        return object()

    factory = AgentFactory(
        repository,
        provider_model_factory=fake_provider_model_factory,
        create_agent_factory=lambda **kwargs: object(),
    )

    await factory.create_agent()

    assert provider_model_calls[0][0] == "deepseek-v4-pro"
    assert provider_model_calls[0][1].id == enabled_provider.id
    assert provider_model_calls[0][1].enabled is True


@pytest.mark.asyncio
async def test_agent_factory_create_deepagents_returns_fresh_agent_each_call() -> None:
    repository = FakeRepository([FakeProvider(models=["deepseek-v4-pro"])])
    created_agents = [object(), object()]
    create_deep_agent_calls: list[dict] = []

    def fake_provider_model_factory(
        model: str, provider: object, **model_config: object
    ) -> object:
        return {"model": model, "temperature": model_config.get("temperature")}

    def fake_create_deep_agent(
        *, model: object, tools: object, system_prompt: object
    ) -> object:
        create_deep_agent_calls.append(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
            }
        )
        return created_agents[len(create_deep_agent_calls) - 1]

    factory = AgentFactory(
        repository,
        provider_model_factory=fake_provider_model_factory,
        create_deep_agent_factory=fake_create_deep_agent,
    )

    first = await factory.create_deepagents(
        system_prompt="Review one.",
        model_config={"temperature": 0},
    )
    second = await factory.create_deepagents(
        system_prompt="Review two.",
        model_config={"temperature": 0},
    )

    assert first is created_agents[0]
    assert second is created_agents[1]
    assert len(create_deep_agent_calls) == 2
    assert create_deep_agent_calls[0]["system_prompt"] == "Review one."
    assert create_deep_agent_calls[1]["system_prompt"] == "Review two."


@pytest.mark.asyncio
async def test_agent_factory_fails_without_provider() -> None:
    factory = AgentFactory(FakeRepository([]))

    with pytest.raises(LlmProviderAgentConfigurationError, match="No LLM provider"):
        await factory.create_agent()


@pytest.mark.asyncio
async def test_agent_factory_fails_without_provider_model() -> None:
    factory = AgentFactory(FakeRepository([FakeProvider(models=[])]))

    with pytest.raises(
        LlmProviderAgentConfigurationError, match="does not list models"
    ):
        await factory.create_deepagents()


@pytest.mark.asyncio
async def test_agent_factory_fails_when_all_providers_are_disabled() -> None:
    factory = AgentFactory(FakeRepository([FakeProvider(enabled=False)]))

    with pytest.raises(
        LlmProviderAgentConfigurationError,
        match="No enabled LLM provider",
    ):
        await factory.create_deepagents()

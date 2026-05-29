from collections.abc import Callable, Sequence
from typing import get_args, get_origin, get_type_hints
from uuid import uuid4

import pytest
from langchain_core.tools import BaseTool

from app.agent.manager.agent_factory import (
    AgentFactory,
    AgentTool,
    LlmProviderAgentConfigurationError,
)
from app.core.json_types import JsonObject
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


def test_agent_factory_tools_annotation_uses_langchain_tool_interface() -> None:
    agent_tool_args = get_args(AgentTool)
    assert BaseTool in agent_tool_args
    assert JsonObject in agent_tool_args
    assert any(get_origin(arg) is Callable for arg in agent_tool_args)

    for factory_method in (AgentFactory.create_agent, AgentFactory.create_deepagents):
        hints = get_type_hints(factory_method)
        tools_hint = hints["tools"]
        tools_args = get_args(tools_hint)
        sequence_hint = next(arg for arg in tools_args if get_origin(arg) is Sequence)
        assert get_args(sequence_hint) == (AgentTool,)


@pytest.mark.asyncio
async def test_agent_factory_create_agent_uses_first_provider_and_model() -> None:
    first_provider = FakeProvider(models=["deepseek-v4-pro", "deepseek-chat"])
    repository = FakeRepository([first_provider, FakeProvider(models=["gpt-5-mini"])])
    created_agent = object()
    configured_model = object()
    provider_model_calls: list[tuple[str, LlmProviderRuntimeConfig, dict]] = []
    create_agent_calls: list[dict] = []
    tools = [lambda: "tool"]

    def fake_provider_model_factory(model: str, provider, **model_config):
        provider_model_calls.append((model, provider, dict(model_config)))
        return configured_model

    def fake_create_agent(*, model, tools, system_prompt):
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
        system_prompt="请仔细评审 SOP。",
        tools=tools,
        model_config={"temperature": 0},
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
    assert create_agent_calls == [
        {
            "model": configured_model,
            "tools": tools,
            "system_prompt": "请仔细评审 SOP。",
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

    def fake_provider_model_factory(model: str, provider, **model_config):
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

    def fake_provider_model_factory(model: str, provider, **model_config):
        return {"model": model, "temperature": model_config.get("temperature")}

    def fake_create_deep_agent(*, model, tools, system_prompt):
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
        system_prompt="请评审第一份内容。",
        model_config={"temperature": 0},
    )
    second = await factory.create_deepagents(
        system_prompt="请评审第二份内容。",
        model_config={"temperature": 0},
    )

    assert first is created_agents[0]
    assert second is created_agents[1]
    assert len(create_deep_agent_calls) == 2
    assert create_deep_agent_calls[0]["system_prompt"] == "请评审第一份内容。"
    assert create_deep_agent_calls[1]["system_prompt"] == "请评审第二份内容。"


@pytest.mark.asyncio
async def test_agent_factory_fails_without_provider() -> None:
    factory = AgentFactory(FakeRepository([]))

    with pytest.raises(LlmProviderAgentConfigurationError, match="No LLM provider"):
        await factory.create_agent()


@pytest.mark.asyncio
async def test_agent_factory_fails_without_provider_model() -> None:
    factory = AgentFactory(FakeRepository([FakeProvider(models=[])]))

    with pytest.raises(LlmProviderAgentConfigurationError, match="does not list models"):
        await factory.create_deepagents()


@pytest.mark.asyncio
async def test_agent_factory_fails_when_all_providers_are_disabled() -> None:
    factory = AgentFactory(FakeRepository([FakeProvider(enabled=False)]))

    with pytest.raises(
        LlmProviderAgentConfigurationError,
        match="No enabled LLM provider",
    ):
        await factory.create_deepagents()

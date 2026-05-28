from typing import Any, Protocol

from deepagents import create_deep_agent as deepagents_create_deep_agent
from langchain.agents import create_agent as langchain_create_agent

from app.core.llm_models import LlmProviderRuntimeConfig, create_provider_chat_model


class LlmProviderAgentConfigurationError(RuntimeError):
    pass


class LlmProviderLike(Protocol):
    id: Any
    provider_type: str
    base_url: str | None
    api_key: str | None
    default_headers: dict[str, str]
    default_query: dict[str, str]
    enabled: bool
    models: list[str]


class LlmProviderRepositoryLike(Protocol):
    async def list(self) -> list[LlmProviderLike]:
        pass


class AgentFactory:
    def __init__(
        self,
        repository: LlmProviderRepositoryLike,
        *,
        provider_model_factory=create_provider_chat_model,
        create_agent_factory=langchain_create_agent,
        create_deep_agent_factory=deepagents_create_deep_agent,
    ) -> None:
        self._repository = repository
        self._provider_model_factory = provider_model_factory
        self._create_agent_factory = create_agent_factory
        self._create_deep_agent_factory = create_deep_agent_factory

    async def create_agent(
        self,
        *,
        system_prompt: str = "You are a careful SOP quality reviewer.",
        tools: list[Any] | None = None,
        model_config: dict[str, Any] | None = None,
    ) -> Any:
        configured_model = await self._configured_model(model_config)
        return self._create_agent_factory(
            model=configured_model,
            tools=list(tools or []),
            system_prompt=system_prompt,
        )

    async def create_deepagents(
        self,
        *,
        system_prompt: str = "You are a careful SOP quality reviewer.",
        tools: list[Any] | None = None,
        model_config: dict[str, Any] | None = None,
    ) -> Any:
        configured_model = await self._configured_model(model_config)
        return self._create_deep_agent_factory(
            model=configured_model,
            tools=list(tools or []),
            system_prompt=system_prompt,
        )

    async def _configured_model(self, model_config: dict[str, Any] | None) -> Any:
        provider = await self._first_provider()
        return self._provider_model_factory(
            _first_model(provider),
            _runtime_config(provider),
            **dict(model_config or {}),
        )

    async def _first_provider(self) -> LlmProviderLike:
        providers = await self._repository.list()
        if not providers:
            raise LlmProviderAgentConfigurationError("No LLM provider is configured.")
        return providers[0]


def _first_model(provider: LlmProviderLike) -> str:
    for model in provider.models or []:
        if model:
            return model
    raise LlmProviderAgentConfigurationError(
        f"LLM provider {provider.id} does not list models."
    )


def _runtime_config(provider: LlmProviderLike) -> LlmProviderRuntimeConfig:
    return LlmProviderRuntimeConfig(
        id=provider.id,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        api_key=provider.api_key,
        default_headers=dict(provider.default_headers or {}),
        default_query=dict(provider.default_query or {}),
        enabled=provider.enabled,
    )

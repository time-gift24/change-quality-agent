from typing import Any, Protocol

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


async def create_agent_by_llm_provider(
    repository: LlmProviderRepositoryLike,
    *,
    system_prompt: str = "You are a careful SOP quality reviewer.",
    tools: list[Any] | None = None,
    model_config: dict[str, Any] | None = None,
    provider_model_factory=create_provider_chat_model,
    create_agent=langchain_create_agent,
) -> Any:
    providers = await repository.list()
    if not providers:
        raise LlmProviderAgentConfigurationError("No LLM provider is configured.")

    provider = providers[0]
    model = _first_model(provider)
    configured_model = provider_model_factory(
        model,
        _runtime_config(provider),
        **dict(model_config or {}),
    )
    return create_agent(
        model=configured_model,
        tools=list(tools or []),
        system_prompt=system_prompt,
    )


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

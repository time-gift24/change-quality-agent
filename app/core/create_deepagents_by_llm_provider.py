from typing import Any

from deepagents import create_deep_agent as deepagents_create_deep_agent

from app.core.create_agent_by_llm_provider import (
    LlmProviderAgentConfigurationError,
    LlmProviderRepositoryLike,
    _first_model,
    _runtime_config,
)
from app.core.llm_models import create_provider_chat_model


async def create_deepagents_by_llm_provider(
    repository: LlmProviderRepositoryLike,
    *,
    system_prompt: str = "You are a careful SOP quality reviewer.",
    tools: list[Any] | None = None,
    model_config: dict[str, Any] | None = None,
    provider_model_factory=create_provider_chat_model,
    create_deep_agent=deepagents_create_deep_agent,
) -> Any:
    providers = await repository.list()
    if not providers:
        raise LlmProviderAgentConfigurationError("No LLM provider is configured.")

    provider = providers[0]
    configured_model = provider_model_factory(
        _first_model(provider),
        _runtime_config(provider),
        **dict(model_config or {}),
    )
    return create_deep_agent(
        model=configured_model,
        tools=list(tools or []),
        system_prompt=system_prompt,
    )

import importlib.util
import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from agent.react_runtime import AgentRuntime, AgentRuntimeProviderUnavailableError


class FakeVersion:
    def __init__(self) -> None:
        self.id = uuid4()
        self.provider_id = uuid4()
        self.model_config = {"temperature": 0.2}
        self.system_prompt = "Review risky changes carefully."
        self.tool_allowlist = ["search_sop"]
        self.mcp_server_ids = ["change-docs"]


class FakeResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], list[str]]] = []
        self.tools = [lambda: "resolved"]

    def resolve(self, tool_allowlist, mcp_server_ids):
        self.calls.append((list(tool_allowlist), list(mcp_server_ids)))
        return self.tools


class AsyncFakeResolver(FakeResolver):
    async def resolve(self, tool_allowlist, mcp_server_ids):
        self.calls.append((list(tool_allowlist), list(mcp_server_ids)))
        return self.tools


class FakeProvider:
    def __init__(
        self,
        *,
        model: str | None = "gpt-5-mini",
        provider: str | None = "openai",
        base_url: str | None = "https://api.openai.com/v1",
    ) -> None:
        self.id = uuid4()
        self.model = model
        self.provider = provider
        self.base_url = base_url
        self.api_key_ciphertext = "secret-key"


class FakeProviderResolver:
    def __init__(self, provider: FakeProvider | None = None) -> None:
        self.provider = provider or FakeProvider()
        self.calls: list[tuple[object, str | None]] = []

    async def resolve(self, provider_id, owner_user_id):
        self.calls.append((provider_id, owner_user_id))
        return self.provider


class FakeAgent:
    def __init__(self, output):
        self.output = output
        self.inputs: list[dict[str, object]] = []

    async def ainvoke(self, payload):
        self.inputs.append(payload)
        return self.output


def test_openai_provider_integration_is_available_without_network() -> None:
    spec = importlib.util.find_spec("langchain_openai")

    assert spec is not None


@pytest.mark.asyncio
async def test_runtime_creates_agent_with_version_config_and_invokes_messages() -> None:
    version = FakeVersion()
    resolver = FakeResolver()
    created: dict[str, object] = {}
    raw_output = {
        "messages": [
            {"role": "user", "content": "Can this deploy?"},
            {"role": "assistant", "content": "Review passed."},
        ],
        "status": "ok",
    }
    agent = FakeAgent(raw_output)

    def fake_create_agent(*, model, tools, system_prompt):
        created["model"] = model
        created["tools"] = tools
        created["system_prompt"] = system_prompt
        return agent

    runtime = AgentRuntime(
        create_agent=fake_create_agent,
        tool_resolver=resolver,
        provider_resolver=FakeProviderResolver(),
        model_factory=lambda model, **_: model,
    )
    input_messages = [{"role": "user", "content": "Can this deploy?"}]

    result = await runtime.run(version=version, messages=input_messages)

    assert resolver.calls == [(["search_sop"], ["change-docs"])]
    assert created == {
        "model": "gpt-5-mini",
        "tools": resolver.tools,
        "system_prompt": "Review risky changes carefully.",
    }
    assert agent.inputs == [{"messages": input_messages}]
    assert result.messages == raw_output["messages"]
    assert result.raw_output == raw_output


@pytest.mark.asyncio
async def test_runtime_passes_model_config_to_model_factory_boundary() -> None:
    version = FakeVersion()
    resolver = FakeResolver()
    configured_model = object()
    model_factory_calls: list[tuple[str, dict[str, object]]] = []
    created: dict[str, object] = {}
    provider = FakeProvider()
    provider_resolver = FakeProviderResolver(provider)

    def fake_model_factory(model: str, **model_config):
        model_factory_calls.append((model, dict(model_config)))
        return configured_model

    def fake_create_agent(*, model, tools, system_prompt):
        created["model"] = model
        created["tools"] = tools
        created["system_prompt"] = system_prompt
        return FakeAgent({"messages": []})

    runtime = AgentRuntime(
        create_agent=fake_create_agent,
        model_factory=fake_model_factory,
        tool_resolver=resolver,
        provider_resolver=provider_resolver,
    )

    await runtime.run(
        version=version,
        messages=[{"role": "user", "content": "Hi"}],
        current_user={"user_id": "user-1", "role": "user"},
    )

    assert provider_resolver.calls == [(version.provider_id, "user-1")]
    assert model_factory_calls == [
        (
            "gpt-5-mini",
            {
                "temperature": 0.2,
                "api_key": "secret-key",
                "base_url": "https://api.openai.com/v1",
                "model_provider": "openai",
            },
        ),
    ]
    assert created["model"] is configured_model
    assert created["tools"] == resolver.tools


@pytest.mark.asyncio
async def test_runtime_awaits_async_tool_resolver() -> None:
    resolver = AsyncFakeResolver()
    created: dict[str, object] = {}

    def fake_create_agent(*, model, tools, system_prompt):
        created["tools"] = tools
        return FakeAgent({"messages": []})

    runtime = AgentRuntime(
        create_agent=fake_create_agent,
        tool_resolver=resolver,
        provider_resolver=FakeProviderResolver(),
        model_factory=lambda model, **_: model,
    )

    await runtime.run(
        version=FakeVersion(),
        messages=[{"role": "user", "content": "Hi"}],
    )

    assert resolver.calls == [(["search_sop"], ["change-docs"])]
    assert created["tools"] == resolver.tools


@pytest.mark.asyncio
async def test_runtime_returns_json_serializable_raw_output_for_langchain_messages() -> None:
    raw_output = {
        "messages": [AIMessage(content="Review passed.")],
        "nested": {"message": AIMessage(content="Nested review details.")},
    }
    runtime = AgentRuntime(
        create_agent=lambda **_: FakeAgent(raw_output),
        tool_resolver=FakeResolver(),
        provider_resolver=FakeProviderResolver(),
        model_factory=lambda model, **_: model,
    )

    result = await runtime.run(
        version=FakeVersion(),
        messages=[{"role": "user", "content": "Can this deploy?"}],
    )

    json.dumps(result.raw_output)
    assert result.messages[0]["content"] == "Review passed."
    assert result.raw_output["messages"][0]["content"] == "Review passed."
    assert result.raw_output["nested"]["message"]["content"] == "Nested review details."


@pytest.mark.asyncio
async def test_runtime_supports_agents_with_sync_invoke_only() -> None:
    class SyncAgent:
        def __init__(self) -> None:
            self.payload = None

        def invoke(self, payload):
            self.payload = payload
            return {"messages": [{"role": "assistant", "content": "Done."}]}

    agent = SyncAgent()
    runtime = AgentRuntime(
        create_agent=lambda **_: agent,
        tool_resolver=FakeResolver(),
        provider_resolver=FakeProviderResolver(),
        model_factory=lambda model, **_: model,
    )
    messages = [{"role": "user", "content": "Run the check."}]

    result = await runtime.run(version=FakeVersion(), messages=messages)

    assert agent.payload == {"messages": messages}
    assert result.messages == [{"role": "assistant", "content": "Done."}]


@pytest.mark.asyncio
async def test_runtime_omits_optional_provider_kwargs_when_absent() -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    provider = FakeProvider(provider=None, base_url=None)

    def fake_model_factory(model: str, **kwargs):
        calls.append((model, dict(kwargs)))
        return model

    runtime = AgentRuntime(
        create_agent=lambda **_: FakeAgent({"messages": []}),
        tool_resolver=FakeResolver(),
        provider_resolver=FakeProviderResolver(provider),
        model_factory=fake_model_factory,
    )

    await runtime.run(version=FakeVersion(), messages=[])

    assert calls == [
        ("gpt-5-mini", {"temperature": 0.2, "api_key": "secret-key"})
    ]


@pytest.mark.asyncio
async def test_runtime_default_provider_resolver_fails_clearly() -> None:
    runtime = AgentRuntime(
        create_agent=lambda **_: FakeAgent({"messages": []}),
        tool_resolver=FakeResolver(),
        model_factory=lambda model, **_: model,
    )

    with pytest.raises(
        AgentRuntimeProviderUnavailableError,
        match="LLM provider is not configured",
    ):
        await runtime.run(version=FakeVersion(), messages=[])


@pytest.mark.asyncio
async def test_runtime_rejects_provider_without_model() -> None:
    runtime = AgentRuntime(
        create_agent=lambda **_: FakeAgent({"messages": []}),
        tool_resolver=FakeResolver(),
        provider_resolver=FakeProviderResolver(FakeProvider(model=None)),
        model_factory=lambda model, **_: model,
    )

    with pytest.raises(
        AgentRuntimeProviderUnavailableError,
        match="does not declare a model",
    ):
        await runtime.run(version=FakeVersion(), messages=[])

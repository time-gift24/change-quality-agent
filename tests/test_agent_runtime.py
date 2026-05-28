import importlib.util
import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from app.core.agent_runtime import AgentRuntime
from app.core.llm_models import LlmProviderRuntimeConfig
from app.core.llm_models import create_chat_model


class FakeVersion:
    def __init__(self) -> None:
        self.id = uuid4()
        self.model = "openai:gpt-5-mini"
        self.provider_id = None
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


class FakeProviderResolver:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.provider = LlmProviderRuntimeConfig(
            id=uuid4(),
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            default_headers={},
            default_query={},
            enabled=True,
        )

    async def resolve(self, provider_id) -> LlmProviderRuntimeConfig:
        self.calls.append(provider_id)
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


def test_runtime_uses_project_chat_model_factory_by_default() -> None:
    assert AgentRuntime.__init__.__kwdefaults__["model_factory"] is create_chat_model


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
        model_factory=lambda model, **_: model,
    )
    input_messages = [{"role": "user", "content": "Can this deploy?"}]

    result = await runtime.run(version=version, messages=input_messages)

    assert resolver.calls == [(["search_sop"], ["change-docs"])]
    assert created == {
        "model": "openai:gpt-5-mini",
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
    )

    await runtime.run(version=version, messages=[{"role": "user", "content": "Hi"}])

    assert model_factory_calls == [
        ("openai:gpt-5-mini", {"temperature": 0.2}),
    ]
    assert created["model"] is configured_model
    assert created["tools"] == resolver.tools


@pytest.mark.asyncio
async def test_runtime_uses_provider_resolver_when_provider_id_is_set() -> None:
    version = FakeVersion()
    version.model = "gpt-5-mini"
    provider_id = uuid4()
    version.provider_id = provider_id
    provider_resolver = FakeProviderResolver()
    provider_model = object()
    default_factory_calls: list[str] = []
    provider_factory_calls: list[tuple[str, LlmProviderRuntimeConfig, dict[str, object]]] = []
    created: dict[str, object] = {}

    def fake_provider_model_factory(model: str, provider, **model_config):
        provider_factory_calls.append((model, provider, dict(model_config)))
        return provider_model

    def fake_create_agent(*, model, tools, system_prompt):
        created["model"] = model
        return FakeAgent({"messages": []})

    runtime = AgentRuntime(
        create_agent=fake_create_agent,
        model_factory=lambda model, **_: default_factory_calls.append(model),
        provider_resolver=provider_resolver,
        provider_model_factory=fake_provider_model_factory,
    )

    await runtime.run(version=version, messages=[])

    assert provider_resolver.calls == [provider_id]
    assert provider_factory_calls == [
        ("gpt-5-mini", provider_resolver.provider, {"temperature": 0.2})
    ]
    assert default_factory_calls == []
    assert created["model"] is provider_model


@pytest.mark.asyncio
async def test_runtime_requires_provider_resolver_when_provider_id_is_set() -> None:
    version = FakeVersion()
    version.model = "gpt-5-mini"
    version.provider_id = uuid4()
    runtime = AgentRuntime(
        create_agent=lambda **_: FakeAgent({"messages": []}),
        model_factory=lambda model, **_: model,
    )

    with pytest.raises(RuntimeError, match="LLM provider resolver is not configured"):
        await runtime.run(version=version, messages=[])


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
        model_factory=lambda model, **_: model,
    )
    messages = [{"role": "user", "content": "Run the check."}]

    result = await runtime.run(version=FakeVersion(), messages=messages)

    assert agent.payload == {"messages": messages}
    assert result.messages == [{"role": "assistant", "content": "Done."}]


@pytest.mark.asyncio
async def test_agent_runtime_stream_yields_message_deltas() -> None:
    class StreamingAgent:
        async def astream(self, payload, stream_mode=None):
            yield ("messages", ("alpha", {"langgraph_node": "agent"}))
            yield ("messages", ("beta", {"langgraph_node": "agent"}))

    runtime = AgentRuntime(
        create_agent=lambda **_: StreamingAgent(),
        model_factory=lambda *_, **__: object(),
    )

    chunks = [
        chunk
        async for chunk in runtime.stream(version=FakeVersion(), messages=[])
    ]

    assert [chunk["type"] for chunk in chunks] == ["messages", "messages"]
    assert [chunk["node"] for chunk in chunks] == ["agent", "agent"]
    assert [chunk["payload"]["delta"] for chunk in chunks] == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_agent_runtime_stream_extracts_content_block_message_deltas() -> None:
    class StreamingAgent:
        async def astream(self, payload, stream_mode=None):
            yield (
                "messages",
                (
                    AIMessage(content=[{"type": "text", "text": "hello"}]),
                    {"langgraph_node": "agent"},
                ),
            )

    runtime = AgentRuntime(
        create_agent=lambda **_: StreamingAgent(),
        model_factory=lambda *_, **__: object(),
    )

    chunks = [
        chunk
        async for chunk in runtime.stream(version=FakeVersion(), messages=[])
    ]

    assert chunks[0]["payload"]["delta"] == "hello"


@pytest.mark.asyncio
async def test_agent_runtime_stream_falls_back_to_final_run_output() -> None:
    class NonStreamingAgent:
        async def ainvoke(self, payload):
            return {"messages": [{"role": "assistant", "content": "done"}]}

    runtime = AgentRuntime(
        create_agent=lambda **_: NonStreamingAgent(),
        model_factory=lambda *_, **__: object(),
    )

    chunks = [
        chunk
        async for chunk in runtime.stream(version=FakeVersion(), messages=[])
    ]

    assert chunks == [
        {
            "type": "messages",
            "node": "agent",
            "payload": {
                "final": True,
                "messages": [{"role": "assistant", "content": "done"}],
            },
        }
    ]

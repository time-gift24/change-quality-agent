from uuid import uuid4

import pytest

from agent.react_runtime import AgentRuntime


class FakeVersion:
    def __init__(self) -> None:
        self.id = uuid4()
        self.model = "openai:gpt-5-mini"
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


class FakeAgent:
    def __init__(self, output):
        self.output = output
        self.inputs: list[dict[str, object]] = []

    async def ainvoke(self, payload):
        self.inputs.append(payload)
        return self.output


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

    runtime = AgentRuntime(create_agent=fake_create_agent, tool_resolver=resolver)
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
async def test_runtime_supports_agents_with_sync_invoke_only() -> None:
    class SyncAgent:
        def __init__(self) -> None:
            self.payload = None

        def invoke(self, payload):
            self.payload = payload
            return {"messages": [{"role": "assistant", "content": "Done."}]}

    agent = SyncAgent()
    runtime = AgentRuntime(create_agent=lambda **_: agent, tool_resolver=FakeResolver())
    messages = [{"role": "user", "content": "Run the check."}]

    result = await runtime.run(version=FakeVersion(), messages=messages)

    assert agent.payload == {"messages": messages}
    assert result.messages == [{"role": "assistant", "content": "Done."}]

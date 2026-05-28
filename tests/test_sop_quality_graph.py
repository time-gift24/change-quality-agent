import pytest
from langchain_core.messages import AIMessageChunk

from app.agent.sop_quality.graph import build_sop_quality_graph


class FakeLlmProviderRepository:
    pass


class FakeAgent:
    def __init__(self, output: str) -> None:
        self.output = output
        self.inputs: list[dict] = []

    async def ainvoke(self, inputs):
        self.inputs.append(inputs)
        return {"messages": [{"role": "assistant", "content": self.output}]}


class StreamingFakeAgent:
    def __init__(self, chunks: list[object]) -> None:
        self.chunks = chunks
        self.invoke_called = False
        self.stream_modes: list[object] = []

    async def astream(self, inputs, stream_mode=None):
        self.stream_modes.append(stream_mode)
        for chunk in self.chunks:
            yield ("messages", (chunk, {"langgraph_node": "check_steps"}))

    async def ainvoke(self, inputs):
        self.invoke_called = True
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": "".join(str(chunk) for chunk in self.chunks),
                }
            ]
        }


@pytest.mark.asyncio
async def test_sop_quality_graph_returns_agent_result() -> None:
    repository = FakeLlmProviderRepository()
    agent = FakeAgent(
        """
        {
          "quality_result": "warn",
          "summary": "Release SOP needs clearer rollback instructions.",
          "findings": [
            {
              "severity": "medium",
              "title": "Rollback is underspecified",
              "recommendation": "Add owner and exact rollback command."
            }
          ],
          "report_markdown": "## SOP Quality Report\\n\\nRelease SOP needs clearer rollback instructions."
        }
        """
    )
    factory_calls: list[object] = []

    async def fake_create_deep_agent_by_provider(llm_provider_repository, **kwargs):
        factory_calls.append(llm_provider_repository)
        return agent

    graph = build_sop_quality_graph(
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {
                "sop_id": "release-checklist",
                "payload": {"title": "Release", "steps": [{"name": "deploy"}]},
            },
        }
    )

    assert factory_calls == [repository]
    assert result["quality_result"] == "warn"
    assert result["summary"] == "Release SOP needs clearer rollback instructions."
    assert result["findings"][0]["title"] == "Rollback is underspecified"
    assert result["result"]["quality_result"] == "warn"
    assert agent.inputs[0]["messages"][0]["content"].find("release-checklist") > -1


@pytest.mark.asyncio
async def test_sop_quality_graph_fails_when_agent_returns_invalid_json() -> None:
    repository = FakeLlmProviderRepository()
    agent = FakeAgent("This SOP looks fine.")

    async def fake_create_deep_agent_by_provider(llm_provider_repository, **kwargs):
        return agent

    graph = build_sop_quality_graph(
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
    )

    with pytest.raises(ValueError, match="valid JSON"):
        await graph.ainvoke(
            {
                "check_id": "check-1",
                "sop_id": "release-checklist",
                "env_key": "dev",
                "sop_snapshot": {
                    "sop_id": "release-checklist",
                    "payload": {"title": "Release"},
                },
            }
        )


@pytest.mark.asyncio
async def test_sop_quality_graph_normalizes_common_agent_severity_variants() -> None:
    repository = FakeLlmProviderRepository()
    agent = FakeAgent(
        """
        {
          "quality_result": "fail",
          "summary": "Release SOP has blocking gaps.",
          "findings": [
            {
              "severity": "Critical",
              "title": "No rollback path",
              "recommendation": "Add rollback owner and exact commands."
            },
            {
              "severity": "中",
              "title": "缺少检查人",
              "recommendation": "补充审批和检查责任人。"
            }
          ],
          "report_markdown": "## SOP Quality Report"
        }
        """
    )

    async def fake_create_deep_agent_by_provider(llm_provider_repository, **kwargs):
        return agent

    graph = build_sop_quality_graph(
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {
                "sop_id": "release-checklist",
                "payload": {"title": "Release"},
            },
        }
    )

    assert [item["severity"] for item in result["findings"]] == ["high", "medium"]


@pytest.mark.asyncio
async def test_sop_quality_graph_streams_thinking_status_and_final_summary() -> None:
    repository = FakeLlmProviderRepository()
    chunks = [
        AIMessageChunk(
            content="",
            additional_kwargs={"reasoning_content": "private chain of thought"},
        ),
        '{"quality_result":"pass","summary":"',
        'Looks ready.',
        '","findings":[],"report_markdown":"## SOP Quality Report"}',
    ]
    agent = StreamingFakeAgent(chunks)
    live_events: list[dict] = []

    async def fake_create_deep_agent_by_provider(llm_provider_repository, **kwargs):
        return agent

    graph = build_sop_quality_graph(
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
        on_live_event=live_events.append,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {
                "sop_id": "release-checklist",
                "payload": {"title": "Release"},
            },
        }
    )

    assert result["quality_result"] == "pass"
    assert agent.invoke_called is False
    assert agent.stream_modes == [["messages", "updates"]]
    assert live_events == [
        {
            "type": "messages",
            "node": "check_steps",
            "channel": "thinking",
            "message": "正在分析 SOP...",
        },
        {
            "type": "messages",
            "node": "check_steps",
            "channel": "summary",
            "message": "## SOP Quality Report",
        },
    ]

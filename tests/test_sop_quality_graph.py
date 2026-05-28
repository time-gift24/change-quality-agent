import pytest
from langchain_core.messages import AIMessageChunk

from app.agent.sop_quality.graph import build_sop_quality_graph
from app.schemas.sop import SopSnapshot


class FakeLlmProviderRepository:
    pass


class FakeSopClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        self.calls.append((sop_id, env_key))
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="test",
            updated_at=None,
            payload={"title": "Release", "steps": [{"name": "deploy"}]},
        )


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
            yield ("messages", (chunk, {"langgraph_node": "review_sop"}))

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


async def fake_submit_quality_result(payload):
    return {"external_status": "submitted", "quality_result": payload["quality_result"]}


@pytest.mark.asyncio
async def test_sop_quality_graph_returns_agent_result() -> None:
    repository = FakeLlmProviderRepository()
    sop_client = FakeSopClient()
    agent = FakeAgent("Release SOP needs clearer rollback instructions.")
    factory_calls: list[object] = []
    submissions: list[dict] = []

    async def fake_create_deep_agent_by_provider(llm_provider_repository, **kwargs):
        factory_calls.append(llm_provider_repository)
        return agent

    async def submit_quality_result(payload):
        submissions.append(payload)
        return {"external_status": "submitted"}

    graph = build_sop_quality_graph(
        sop_client=sop_client,
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
        submit_quality_result=submit_quality_result,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
        }
    )

    assert factory_calls == [repository]
    assert result["quality_result"] == "warn"
    assert result["summary"] == "Release SOP needs clearer rollback instructions."
    assert result["findings"] == []
    assert result["result"]["quality_result"] == "warn"
    assert result["sop_snapshot"]["payload"]["title"] == "Release"
    assert result["submission_result"] == {"external_status": "submitted"}
    assert submissions[0]["quality_result"] == "warn"
    assert sop_client.calls == [("release-checklist", "dev")]
    assert agent.inputs[0]["messages"][0]["content"].find("release-checklist") > -1


@pytest.mark.asyncio
async def test_sop_quality_graph_wraps_unstructured_agent_output() -> None:
    repository = FakeLlmProviderRepository()
    sop_client = FakeSopClient()
    agent = FakeAgent("This SOP looks fine.")

    async def fake_create_deep_agent_by_provider(llm_provider_repository, **kwargs):
        return agent

    graph = build_sop_quality_graph(
        sop_client=sop_client,
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
        submit_quality_result=fake_submit_quality_result,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
        }
    )

    assert result["quality_result"] == "warn"
    assert result["summary"] == "This SOP looks fine."
    assert result["result"]["report_markdown"] == "This SOP looks fine."


@pytest.mark.asyncio
async def test_sop_quality_graph_normalizes_common_agent_severity_variants() -> None:
    repository = FakeLlmProviderRepository()
    sop_client = FakeSopClient()
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
        sop_client=sop_client,
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
        submit_quality_result=fake_submit_quality_result,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
        }
    )

    assert [item["severity"] for item in result["findings"]] == ["high", "medium"]


@pytest.mark.asyncio
async def test_sop_quality_graph_streams_content_deltas_without_reasoning_text() -> None:
    repository = FakeLlmProviderRepository()
    sop_client = FakeSopClient()
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
        sop_client=sop_client,
        llm_provider_repository=repository,
        create_deep_agent_by_provider=fake_create_deep_agent_by_provider,
        on_live_event=live_events.append,
        submit_quality_result=fake_submit_quality_result,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
        }
    )

    assert result["quality_result"] == "pass"
    assert agent.invoke_called is False
    assert agent.stream_modes == [["messages", "updates"]]
    assert live_events == [
        {
            "type": "messages",
            "node": "review_sop",
            "channel": "thinking",
            "message": "正在分析 SOP...",
        },
        {
            "type": "messages",
            "node": "review_sop",
            "message": '{"quality_result":"pass","summary":"',
        },
        {
            "type": "messages",
            "node": "review_sop",
            "message": "Looks ready.",
        },
        {
            "type": "messages",
            "node": "review_sop",
            "message": '","findings":[],"report_markdown":"## SOP Quality Report"}',
        },
        {
            "type": "messages",
            "node": "summarize_result",
            "channel": "summary",
            "message": "## SOP Quality Report",
        },
        {
            "type": "messages",
            "node": "submit_result",
            "channel": "summary",
            "message": "External submission: submitted.",
        },
    ]

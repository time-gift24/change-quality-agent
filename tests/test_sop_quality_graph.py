from typing import Any

import pytest

from app.agent.sop_quality.graph import build_sop_quality_graph
from app.core.agent_streaming import DeepAgentRunInput, DeepAgentRunResult
from app.schemas.sop import SopSnapshot


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
    pass


class FakeAgentFactory:
    def __init__(self, agents: list[Any] | None = None) -> None:
        self.agents = agents or [FakeAgent()]
        self.calls: list[dict[str, Any]] = []

    async def create_deepagents(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        return self.agents[len(self.calls) - 1]


class FakeMessageWriter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def append_step_message(
        self,
        *,
        step: str,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ):
        self.calls.append(
            {
                "step": step,
                "role": role,
                "content": content,
                "additional_kwargs": additional_kwargs or {},
            }
        )

        class _Msg:
            sequence = len(self.calls)

        return _Msg()


class FakeStreamRunner:
    def __init__(self, final_text: str) -> None:
        self.final_text = final_text
        self.calls: list[dict[str, Any]] = []

    async def run_step(
        self,
        *,
        agent: Any,
        step: str,
        input: DeepAgentRunInput,
    ) -> DeepAgentRunResult:
        self.calls.append({"agent": agent, "step": step, "input": input})
        return DeepAgentRunResult(final_text=self.final_text)


async def fake_submit_quality_result(payload):
    return {
        "external_status": "submitted",
        "quality_result": payload["quality_result"],
    }


@pytest.mark.asyncio
async def test_review_sop_uses_deepagent_stream_runner() -> None:
    sop_client = FakeSopClient()
    agent_factory = FakeAgentFactory()
    writer = FakeMessageWriter()
    runner = FakeStreamRunner("Release SOP needs clearer rollback instructions.")

    graph = build_sop_quality_graph(
        sop_client=sop_client,
        agent_factory=agent_factory,
        submit_quality_result=fake_submit_quality_result,
        message_writer=writer,
        deepagent_stream_runner=runner,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
        }
    )

    assert runner.calls, "review_sop should call the deepagent stream runner"
    call = runner.calls[0]
    assert call["step"] == "review_sop"
    assert isinstance(call["input"], DeepAgentRunInput)
    assert result["quality_result"] == "warn"
    assert result["summary"] == "Release SOP needs clearer rollback instructions."


@pytest.mark.asyncio
async def test_review_sop_no_longer_imports_runtime_stream_event() -> None:
    import importlib
    import inspect as inspect_mod

    module = importlib.import_module("app.agent.sop_quality.nodes.review_sop")
    source = inspect_mod.getsource(module)

    assert "runtime_stream_event" not in source
    assert "on_live_event" not in source


@pytest.mark.asyncio
async def test_ordinary_nodes_append_step_messages_via_writer() -> None:
    sop_client = FakeSopClient()
    agent_factory = FakeAgentFactory()
    writer = FakeMessageWriter()
    runner = FakeStreamRunner(
        '{"quality_result":"pass","summary":"Looks ready.",'
        '"findings":[],"report_markdown":"## SOP Quality Report"}'
    )

    graph = build_sop_quality_graph(
        sop_client=sop_client,
        agent_factory=agent_factory,
        submit_quality_result=fake_submit_quality_result,
        message_writer=writer,
        deepagent_stream_runner=runner,
    )

    await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
        }
    )

    steps = [call["step"] for call in writer.calls]
    assert "load_sop" in steps
    assert "summarize_result" in steps
    assert "submit_result" in steps

    for call in writer.calls:
        assert "delta" not in (call.get("additional_kwargs") or {})


@pytest.mark.asyncio
async def test_graph_uses_no_op_defaults_when_dependencies_omitted() -> None:
    """Tests without transcript wiring should still work via no-op defaults."""
    sop_client = FakeSopClient()
    agent_factory = FakeAgentFactory()
    runner = FakeStreamRunner("Plain review text.")

    graph = build_sop_quality_graph(
        sop_client=sop_client,
        agent_factory=agent_factory,
        submit_quality_result=fake_submit_quality_result,
        deepagent_stream_runner=runner,
    )

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
        }
    )

    assert result["quality_result"] == "warn"
    assert result["summary"] == "Plain review text."

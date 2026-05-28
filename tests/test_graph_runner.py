from uuid import uuid4

import pytest

from app.models.agents import Agent
from app.agent.sop_quality import run_sop_quality_graph, stream_sop_quality_agent
from app.schemas.runs import RunStatus


class FakeVersion:
    def __init__(self) -> None:
        self.id = uuid4()
        self.agent_id = uuid4()
        self.version_number = 1
        self.model = "openai:deepseek-chat"
        self.system_prompt = "Review SOP quality."
        self.model_config = {"temperature": 0}
        self.tool_allowlist = []
        self.mcp_server_ids = []


class FakeAgent:
    def __init__(self, version: FakeVersion | None) -> None:
        self.id = uuid4()
        self.enabled = True
        self.latest_version = version


class FakeRun:
    def __init__(self) -> None:
        self.id = uuid4()
        self.thread_id = "thread-1"
        self.subject_id = "release-checklist"
        self.subject_snapshot = {
            "sop_id": "release-checklist",
            "payload": {"steps": [{"id": "prepare"}]},
        }


class FakeRepository:
    def __init__(self, run: FakeRun) -> None:
        self.run = run
        self.marked_running = False
        self.events = []
        self.terminal_status = None
        self.raw_graph_output = None
        self.terminal_kwargs = None
        self.committed = False
        self.operations = []

    async def mark_running(self, run_id):
        assert run_id == self.run.id
        self.marked_running = True
        return self.run

    async def append_event(self, run_id, **kwargs):
        assert run_id == self.run.id
        self.events.append(kwargs)
        self.operations.append(f"append_event:{kwargs['event_type']}")
        return kwargs

    async def mark_terminal(self, run_id, status, **kwargs):
        assert run_id == self.run.id
        self.terminal_status = status
        self.terminal_kwargs = kwargs
        self.raw_graph_output = kwargs.get("raw_graph_output")
        self.operations.append(f"mark_terminal:{status.value}")
        return self.run

    async def commit(self) -> None:
        self.committed = True
        self.operations.append("commit")


class FakeAgentRepository:
    def __init__(self, agent: Agent | FakeAgent | None) -> None:
        self.agent = agent
        self.lookups: list[object] = []

    async def get_agent(self, agent_id):
        self.lookups.append(agent_id)
        return self.agent


class FakeStreamingRuntime:
    def __init__(self, events: list[dict[str, object]] | None = None) -> None:
        self.events = events or [
            {
                "type": "messages",
                "node": "model",
                "payload": {"delta": "SOP looks"},
            },
            {
                "type": "messages",
                "node": "model",
                "payload": {"delta": " reviewable."},
            },
        ]
        self.calls: list[dict[str, object]] = []

    async def stream(self, *, version, messages):
        self.calls.append({"version": version, "messages": messages})
        for event in self.events:
            yield event


@pytest.mark.asyncio
async def test_sop_quality_agent_facade_builds_review_message() -> None:
    run = FakeRun()
    version = FakeVersion()
    runtime = FakeStreamingRuntime()

    events = [
        event
        async for event in stream_sop_quality_agent(
            runtime=runtime,
            version=version,
            run=run,
        )
    ]

    assert events == runtime.events
    assert runtime.calls[0]["version"] is version
    message = runtime.calls[0]["messages"][0]
    assert message["role"] == "user"
    assert "release-checklist" in message["content"]
    assert "SOP Snapshot JSON" in message["content"]


@pytest.mark.asyncio
async def test_graph_runner_streams_sop_quality_agent_events() -> None:
    run = FakeRun()
    repository = FakeRepository(run)
    version = FakeVersion()
    agent = FakeAgent(version)
    agent_repository = FakeAgentRepository(agent)
    runtime = FakeStreamingRuntime()

    await run_sop_quality_graph(
        run.id,
        repository,
        agent_repository=agent_repository,
        runtime=runtime,
        agent_id=agent.id,
    )

    assert repository.marked_running is True
    assert [event["event_type"] for event in repository.events] == [
        "custom",
        "messages",
        "messages",
        "done",
    ]
    assert agent_repository.lookups == [agent.id]
    assert runtime.calls[0]["version"] is version
    assert runtime.calls[0]["messages"][0]["role"] == "user"
    assert "release-checklist" in runtime.calls[0]["messages"][0]["content"]
    assert repository.events[1]["payload"]["delta"] == "SOP looks"
    assert repository.operations == [
        "append_event:custom",
        "commit",
        "append_event:messages",
        "commit",
        "append_event:messages",
        "commit",
        "append_event:done",
        "mark_terminal:success",
        "commit",
    ]
    assert repository.terminal_kwargs["structured_result"] == {
        "messages": [{"role": "assistant", "content": "SOP looks reviewable."}]
    }
    assert repository.terminal_status == RunStatus.success
    assert repository.committed is True


@pytest.mark.asyncio
async def test_graph_runner_marks_error_when_sop_quality_agent_is_missing() -> None:
    run = FakeRun()
    repository = FakeRepository(run)
    missing_agent_id = uuid4()

    result = await run_sop_quality_graph(
        run.id,
        repository,
        agent_repository=FakeAgentRepository(None),
        runtime=FakeStreamingRuntime(),
        agent_id=missing_agent_id,
    )

    assert result["status"] == "error"
    assert repository.terminal_status == RunStatus.error
    assert repository.terminal_kwargs["error"] == {
        "type": "RuntimeError",
        "message": f"SOP quality agent not found: {missing_agent_id}",
    }
    assert repository.events[-1]["event_type"] == "error"
    assert repository.events[-1]["payload"] == {
        "type": "RuntimeError",
        "message": f"SOP quality agent not found: {missing_agent_id}",
    }
    assert repository.committed is True


@pytest.mark.asyncio
async def test_graph_runner_marks_error_when_agent_stream_yields_error() -> None:
    run = FakeRun()
    repository = FakeRepository(run)
    version = FakeVersion()
    runtime = FakeStreamingRuntime(
        [
            {
                "type": "messages",
                "payload": {"delta": "partial"},
                "node": "model",
            },
            {
                "type": "error",
                "payload": {"type": "RuntimeError", "message": "agent failed"},
                "node": "model",
            },
        ]
    )

    agent = FakeAgent(version)
    result = await run_sop_quality_graph(
        run.id,
        repository,
        agent_repository=FakeAgentRepository(agent),
        runtime=runtime,
        agent_id=agent.id,
    )

    assert result["status"] == "error"
    assert repository.terminal_status == RunStatus.error
    assert repository.terminal_kwargs["error"] == {
        "type": "RuntimeError",
        "message": "agent failed",
    }
    assert [event["event_type"] for event in repository.events] == [
        "custom",
        "messages",
        "error",
    ]


@pytest.mark.asyncio
async def test_graph_runner_does_not_duplicate_streamed_done_event() -> None:
    run = FakeRun()
    repository = FakeRepository(run)
    version = FakeVersion()
    runtime = FakeStreamingRuntime(
        [
            {
                "type": "messages",
                "payload": {
                    "final": True,
                    "messages": [{"role": "assistant", "content": "done"}],
                },
                "node": "model",
            },
            {
                "type": "done",
                "payload": {"status": "done", "result_status": "success"},
            },
        ]
    )

    agent = FakeAgent(version)
    result = await run_sop_quality_graph(
        run.id,
        repository,
        agent_repository=FakeAgentRepository(agent),
        runtime=runtime,
        agent_id=agent.id,
    )

    assert result["status"] == "success"
    assert [event["event_type"] for event in repository.events] == [
        "custom",
        "messages",
        "done",
    ]

import json
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage

from app.core.agent_runtime import AgentRuntimeResult
from app.schemas.runs import RunStatus
from app.services.agents import run_agent_test


class FakeVersion:
    def __init__(self, *, version_number: int = 3) -> None:
        self.id = uuid4()
        self.agent_id = uuid4()
        self.version_number = version_number
        self.model = "openai:gpt-5-mini"
        self.system_prompt = "Review carefully."
        self.tool_allowlist = []
        self.mcp_server_ids = []


class FakeRun:
    def __init__(self, version: FakeVersion) -> None:
        self.id = uuid4()
        self.thread_id = "thread-agent-test"
        self.status = RunStatus.pending.value
        self.subject_id = "release-reviewer"
        self.metadata_ = {
            "agent_key": "release-reviewer",
            "agent_version_id": str(version.id),
            "agent_version_number": version.version_number,
        }
        self.subject_snapshot = {
            "messages": [{"role": "user", "content": "Can this deploy?"}]
        }


class FakeRunRepository:
    def __init__(self, run: FakeRun, order: list[str] | None = None) -> None:
        self.run = run
        self.order = order
        self.events: list[dict[str, object]] = []
        self.terminal: tuple[RunStatus, dict[str, object]] | None = None
        self.commits = 0

    async def mark_running(self, run_id):
        assert run_id == self.run.id
        if self.order is not None:
            self.order.append("mark_running")
        self.run.status = RunStatus.running.value
        return self.run

    async def append_event(
        self,
        run_id,
        *,
        event_type,
        thread_id,
        payload,
        node=None,
        checkpoint_id=None,
        task_id=None,
    ):
        assert run_id == self.run.id
        assert thread_id == self.run.thread_id
        if self.order is not None:
            self.order.append(f"append_event:{event_type}")
        self.events.append(
            {
                "event_type": event_type,
                "payload": payload,
                "node": node,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
            }
        )

    async def mark_terminal(self, run_id, status, **kwargs):
        assert run_id == self.run.id
        if self.order is not None:
            self.order.append(f"mark_terminal:{status.value}")
        self.run.status = status.value
        self.terminal = (status, kwargs)

    async def commit(self):
        if self.order is not None:
            self.order.append("commit")
        self.commits += 1


class FakeAgentRepository:
    def __init__(self, version: FakeVersion | None) -> None:
        self.version = version
        self.lookups: list[UUID] = []

    async def get_version_by_id(self, version_id):
        self.lookups.append(version_id)
        if self.version is not None and version_id == self.version.id:
            return self.version
        return None


class FakeRuntime:
    def __init__(
        self,
        result: AgentRuntimeResult | None = None,
        exc: Exception | None = None,
        order: list[str] | None = None,
    ):
        self.result = result
        self.exc = exc
        self.order = order
        self.calls: list[dict[str, object]] = []

    async def run(self, *, version, messages):
        if self.order is not None:
            self.order.append("runtime_run")
        self.calls.append({"version": version, "messages": messages})
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


class FakeStreamingRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def stream(self, *, version, messages):
        self.calls.append({"version": version, "messages": messages})
        yield {
            "type": "messages",
            "node": "agent",
            "payload": {"delta": "alpha"},
        }
        yield {
            "type": "messages",
            "node": "agent",
            "payload": {"delta": "beta"},
        }
        yield {
            "type": "messages",
            "node": "agent",
            "payload": {
                "final": True,
                "messages": [{"role": "assistant", "content": "alphabeta"}],
            },
        }


class FakeEventStreamingRuntime:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self.events = events
        self.calls: list[dict[str, object]] = []

    async def stream(self, *, version, messages):
        self.calls.append({"version": version, "messages": messages})
        for event in self.events:
            yield event


@pytest.mark.asyncio
async def test_run_agent_test_appends_messages_and_marks_success() -> None:
    version = FakeVersion(version_number=7)
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    agent_repository = FakeAgentRepository(version)
    result = AgentRuntimeResult(
        messages=[{"role": "assistant", "content": "Review passed."}],
        raw_output={"messages": [{"role": "assistant", "content": "Review passed."}]},
    )
    runtime = FakeRuntime(result=result)

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=agent_repository,
        runtime=runtime,
    )

    assert agent_repository.lookups == [version.id]
    assert runtime.calls == [
        {
            "version": version,
            "messages": [{"role": "user", "content": "Can this deploy?"}],
        }
    ]
    assert [event["event_type"] for event in run_repository.events] == [
        "custom",
        "messages",
        "done",
    ]
    assert run_repository.events[0]["payload"] == {
        "message": "Started agent test run.",
        "agent_key": "release-reviewer",
        "agent_version_number": 7,
    }
    assert run_repository.events[1]["payload"] == {"messages": result.messages}
    assert run_repository.events[2]["payload"] == {
        "status": "done",
        "result_status": "success",
    }
    assert run_repository.terminal == (
        RunStatus.success,
        {
            "structured_result": {"messages": result.messages},
            "raw_graph_output": result.raw_output,
            "result_status": "success",
        },
    )
    assert run_repository.commits == 2


@pytest.mark.asyncio
async def test_run_agent_test_persists_runtime_stream_events() -> None:
    version = FakeVersion(version_number=7)
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    agent_repository = FakeAgentRepository(version)
    runtime = FakeStreamingRuntime()

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=agent_repository,
        runtime=runtime,
    )

    assert runtime.calls == [
        {
            "version": version,
            "messages": [{"role": "user", "content": "Can this deploy?"}],
        }
    ]
    assert [event["event_type"] for event in run_repository.events] == [
        "custom",
        "messages",
        "messages",
        "messages",
        "done",
    ]
    assert run_repository.events[1]["payload"] == {"delta": "alpha"}
    assert run_repository.events[2]["payload"] == {"delta": "beta"}
    assert run_repository.events[3]["payload"] == {
        "final": True,
        "messages": [{"role": "assistant", "content": "alphabeta"}],
    }
    assert run_repository.terminal == (
        RunStatus.success,
        {
            "structured_result": {
                "messages": [{"role": "assistant", "content": "alphabeta"}]
            },
            "raw_graph_output": {
                "stream_events": [
                    {
                        "type": "messages",
                        "node": "agent",
                        "payload": {"delta": "alpha"},
                    },
                    {
                        "type": "messages",
                        "node": "agent",
                        "payload": {"delta": "beta"},
                    },
                    {
                        "type": "messages",
                        "node": "agent",
                        "payload": {
                            "final": True,
                            "messages": [
                                {"role": "assistant", "content": "alphabeta"}
                            ],
                        },
                    },
                ]
            },
            "result_status": "success",
        },
    )
    assert run.status == RunStatus.success.value
    assert run_repository.commits == 5


@pytest.mark.asyncio
async def test_run_agent_test_finalizes_messages_from_stream_deltas() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    runtime = FakeEventStreamingRuntime(
        [
            {
                "type": "messages",
                "node": "agent",
                "payload": {"delta": "alpha"},
            },
            {
                "type": "messages",
                "node": "agent",
                "payload": {"delta": "beta"},
            },
        ]
    )

    result = await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=FakeAgentRepository(version),
        runtime=runtime,
    )

    messages = [{"role": "assistant", "content": "alphabeta"}]
    assert result == {"status": "success", "messages": messages}
    assert run_repository.terminal is not None
    status, terminal_kwargs = run_repository.terminal
    assert status == RunStatus.success
    assert terminal_kwargs["structured_result"] == {"messages": messages}
    json.dumps(terminal_kwargs["raw_graph_output"])


@pytest.mark.asyncio
async def test_run_agent_test_persists_unknown_stream_event_as_custom() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    runtime = FakeEventStreamingRuntime(
        [
            {
                "type": "surprise",
                "node": "agent",
                "payload": {"value": 1},
            },
            {
                "type": "messages",
                "node": "agent",
                "payload": {
                    "final": True,
                    "messages": [{"role": "assistant", "content": "done"}],
                },
            },
        ]
    )

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=FakeAgentRepository(version),
        runtime=runtime,
    )

    assert [event["event_type"] for event in run_repository.events] == [
        "custom",
        "custom",
        "messages",
        "done",
    ]
    assert run_repository.events[1]["payload"] == {"value": 1}


@pytest.mark.asyncio
async def test_run_agent_test_does_not_duplicate_streamed_done_event() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    runtime = FakeEventStreamingRuntime(
        [
            {
                "type": "messages",
                "node": "agent",
                "payload": {
                    "final": True,
                    "messages": [{"role": "assistant", "content": "done"}],
                },
            },
            {
                "type": "done",
                "node": "agent",
                "payload": {"status": "done", "result_status": "success"},
            },
        ]
    )

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=FakeAgentRepository(version),
        runtime=runtime,
    )

    assert [event["event_type"] for event in run_repository.events] == [
        "custom",
        "messages",
        "done",
    ]


@pytest.mark.asyncio
async def test_run_agent_test_marks_error_when_stream_yields_error() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    runtime = FakeEventStreamingRuntime(
        [
            {
                "type": "messages",
                "node": "agent",
                "payload": {"delta": "partial"},
            },
            {
                "type": "error",
                "node": "agent",
                "payload": {"type": "RuntimeError", "message": "stream failed"},
            },
        ]
    )

    result = await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=FakeAgentRepository(version),
        runtime=runtime,
    )

    assert result == {
        "status": "error",
        "error": {"type": "RuntimeError", "message": "stream failed"},
    }
    assert [event["event_type"] for event in run_repository.events] == [
        "custom",
        "messages",
        "error",
    ]
    assert run_repository.terminal == (
        RunStatus.error,
        {
            "error": {"type": "RuntimeError", "message": "stream failed"},
            "result_status": "error",
        },
    )


@pytest.mark.asyncio
async def test_run_agent_test_preserves_normalized_stream_error_details() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    runtime = FakeEventStreamingRuntime(
        [
            {
                "type": "error",
                "node": "agent",
                "payload": {
                    "error": {"type": "RuntimeError", "message": "boom"},
                    "raw": {"type": "RuntimeError", "message": "boom"},
                },
            },
        ]
    )

    result = await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=FakeAgentRepository(version),
        runtime=runtime,
    )

    assert result == {
        "status": "error",
        "error": {"type": "RuntimeError", "message": "boom"},
    }
    assert run_repository.terminal == (
        RunStatus.error,
        {
            "error": {"type": "RuntimeError", "message": "boom"},
            "result_status": "error",
        },
    )


@pytest.mark.asyncio
async def test_run_agent_test_commits_running_start_before_runtime() -> None:
    order: list[str] = []
    version = FakeVersion(version_number=7)
    run = FakeRun(version)
    run_repository = FakeRunRepository(run, order=order)
    agent_repository = FakeAgentRepository(version)
    result = AgentRuntimeResult(
        messages=[{"role": "assistant", "content": "Review passed."}],
        raw_output={"messages": [{"role": "assistant", "content": "Review passed."}]},
    )
    runtime = FakeRuntime(result=result, order=order)

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=agent_repository,
        runtime=runtime,
    )

    assert order == [
        "mark_running",
        "append_event:custom",
        "commit",
        "runtime_run",
        "append_event:messages",
        "append_event:done",
        "mark_terminal:success",
        "commit",
    ]


@pytest.mark.asyncio
async def test_run_agent_test_sanitizes_raw_graph_output_before_persistence() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    agent_repository = FakeAgentRepository(version)
    result = AgentRuntimeResult(
        messages=[{"role": "assistant", "content": "Review passed."}],
        raw_output={
            "messages": [AIMessage(content="Review passed.")],
            "nested": {"message": AIMessage(content="Nested review details.")},
        },
    )
    runtime = FakeRuntime(result=result)

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=agent_repository,
        runtime=runtime,
    )

    assert run_repository.terminal is not None
    status, terminal_kwargs = run_repository.terminal
    assert status == RunStatus.success
    raw_graph_output = terminal_kwargs["raw_graph_output"]
    json.dumps(raw_graph_output)
    assert raw_graph_output["messages"][0]["content"] == "Review passed."
    assert raw_graph_output["nested"]["message"]["content"] == "Nested review details."


@pytest.mark.asyncio
async def test_run_agent_test_marks_error_when_runtime_raises() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    runtime = FakeRuntime(exc=ValueError("model unavailable"))

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=FakeAgentRepository(version),
        runtime=runtime,
    )

    assert [event["event_type"] for event in run_repository.events] == [
        "custom",
        "error",
    ]
    assert run_repository.events[1]["payload"] == {
        "type": "ValueError",
        "message": "model unavailable",
    }
    assert run_repository.terminal == (
        RunStatus.error,
        {
            "error": {"type": "ValueError", "message": "model unavailable"},
            "result_status": "error",
        },
    )
    assert run_repository.commits == 2


@pytest.mark.asyncio
async def test_run_agent_test_marks_error_when_version_is_missing() -> None:
    version = FakeVersion()
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    runtime = FakeRuntime(result=AgentRuntimeResult(messages=[], raw_output={}))

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=FakeAgentRepository(None),
        runtime=runtime,
    )

    assert run.status == RunStatus.error.value
    assert run_repository.events[0]["event_type"] == "error"
    assert "Agent version not found" in run_repository.events[0]["payload"]["message"]
    assert run_repository.terminal is not None
    status, terminal_kwargs = run_repository.terminal
    assert status == RunStatus.error
    assert terminal_kwargs["result_status"] == "error"
    assert runtime.calls == []
    assert run_repository.commits == 1

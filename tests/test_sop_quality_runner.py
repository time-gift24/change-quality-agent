from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.services import sop_quality_runner
from app.services.sop_quality_runner import run_sop_quality_check


class FakeCheck:
    def __init__(self) -> None:
        self.id = uuid4()
        self.sop_id = "release-checklist"
        self.env_key = "dev"
        self.thread_id = "thread-1"
        self.checkpoint_ns = "sop_quality"
        self.current_checkpoint_id = None
        self.session_id = 42
        self.sop_snapshot = {
            "sop_id": "release-checklist",
            "payload": {"title": "Release"},
        }


class FakeRepository:
    def __init__(self, check: FakeCheck) -> None:
        self.check = check
        self.events: list[dict] = []
        self.terminal = None

    async def get_check(self, check_id):
        return self.check if check_id == self.check.id else None

    async def mark_running(self, check_id):
        self.events.append({"type": "mark_running"})
        return self.check

    async def append_event(self, check_id, **kwargs):
        self.events.append(kwargs)
        return type(
            "Event",
            (),
            {
                "check_id": check_id,
                "sequence": len(self.events),
                "type": kwargs["event_type"],
                "node": kwargs.get("node"),
                "checkpoint_id": kwargs.get("checkpoint_id"),
                "task_id": kwargs.get("task_id"),
                "message": kwargs.get("message"),
                "created_at": None,
            },
        )()

    async def set_current_checkpoint(self, check_id, checkpoint_id):
        self.check.current_checkpoint_id = checkpoint_id
        return self.check

    async def mark_terminal(self, check_id, status, **kwargs):
        self.terminal = {"status": status, **kwargs}
        return self.check

    async def commit(self):
        return None


class FakeSessionRepository:
    def __init__(self) -> None:
        self.appended: list[dict] = []
        self.statuses: list[tuple[int, str]] = []
        self.commits = 0

    async def append_message(self, session_id, *, role, content, additional_kwargs=None):
        record = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "additional_kwargs": additional_kwargs or {},
            "sequence": len(self.appended) + 1,
        }
        self.appended.append(record)
        return type("Msg", (), record)()

    async def set_status(self, session_id, status):
        self.statuses.append((session_id, status))
        return type("Session", (), {"id": session_id, "status": status})()

    async def commit(self):
        self.commits += 1


class FakeLlmProviderRepository:
    pass


class FakeAgentFactory:
    def __init__(self, repository) -> None:
        self.repository = repository


class FakeSopClient:
    pass


class FakeBroadcast:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def publish(self, check_id, message):
        self.messages.append(message)


class FakeSessionBroadcast:
    def __init__(self) -> None:
        self.messages: list[tuple[int, dict]] = []

    async def publish(self, session_id, message):
        self.messages.append((session_id, message))


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FailingCheckpointerContext:
    async def __aenter__(self):
        raise RuntimeError("checkpoint setup failed")

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSnapshot:
    config = {"configurable": {"checkpoint_id": "checkpoint-1"}}


class FakeGraph:
    async def ainvoke(self, initial_state, *, config):
        return {
            "quality_result": "warn",
            "result": {
                "quality_result": "warn",
                "summary": "Reviewed by fake graph.",
                "findings": [],
                "report_markdown": "## SOP 质量报告",
            },
        }

    async def aget_state(self, config):
        return FakeSnapshot()


class RuntimePublishingGraph:
    def __init__(self, build_kwargs: dict) -> None:
        self._build_kwargs = build_kwargs

    async def ainvoke(self, initial_state, *, config):
        await self._build_kwargs["message_writer"].append_step_message(
            step="review_sop",
            role="assistant",
            content="final review",
            additional_kwargs={"kind": "final_message"},
        )
        await self._build_kwargs["live_event_publisher"](
            {
                "type": "message_delta",
                "role": "assistant",
                "content": "partial",
                "additional_kwargs": {"step": "review_sop", "channel": "content"},
            }
        )
        return {
            "quality_result": "warn",
            "result": {
                "quality_result": "warn",
                "summary": "Reviewed by fake graph.",
                "findings": [],
                "report_markdown": "## SOP 质量报告",
            },
        }

    async def aget_state(self, config):
        return FakeSnapshot()


async def fake_submit_quality_result(payload):
    return {"external_status": "submitted", "payload": payload}


@pytest.mark.asyncio
async def test_runner_marks_success_and_writes_lifecycle_events(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    llm_provider_repository = FakeLlmProviderRepository()

    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        lambda **kwargs: FakeGraph(),
    )

    result = await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
    )

    assert result["status"] == "succeeded"
    assert repository.events[1]["event_type"] == "started"
    assert repository.terminal["status"] == "succeeded"
    assert repository.terminal["result"]["quality_result"] in {"pass", "warn"}


@pytest.mark.asyncio
async def test_runner_skips_check_that_cannot_transition_to_running(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    llm_provider_repository = FakeLlmProviderRepository()
    build_calls: list[dict] = []

    async def mark_running_skipped(check_id):
        repository.events.append({"type": "mark_running_skipped"})
        return None

    repository.mark_running = mark_running_skipped
    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        lambda **kwargs: build_calls.append(kwargs) or FakeGraph(),
    )

    result = await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
    )

    assert result == {"status": "skipped"}
    assert repository.terminal is None
    assert build_calls == []
    assert repository.events == [{"type": "mark_running_skipped"}]


@pytest.mark.asyncio
async def test_runner_broadcasts_persisted_event_envelopes(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    broadcast = FakeBroadcast()
    llm_provider_repository = FakeLlmProviderRepository()

    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        lambda **kwargs: FakeGraph(),
    )

    await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        broadcast=broadcast,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
    )

    assert broadcast.messages[0]["type"] == "started"
    assert broadcast.messages[0]["check_id"] == check.id
    assert isinstance(broadcast.messages[0]["sequence"], int)
    assert broadcast.messages[-1]["type"] == "completed"
    assert broadcast.messages[-1]["check_id"] == check.id


@pytest.mark.asyncio
async def test_runner_reads_latest_top_level_checkpoint(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    llm_provider_repository = FakeLlmProviderRepository()

    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        lambda **kwargs: FakeGraph(),
    )

    result = await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=InMemorySaver(),
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
    )

    assert result["status"] == "succeeded"
    assert check.current_checkpoint_id


@pytest.mark.asyncio
async def test_runner_passes_runtime_dependencies_to_graph(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    session_repository = FakeSessionRepository()
    llm_provider_repository = FakeLlmProviderRepository()
    build_calls: list[dict] = []

    def fake_build_sop_quality_graph(**kwargs):
        build_calls.append(kwargs)
        return FakeGraph()

    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        fake_build_sop_quality_graph,
    )
    monkeypatch.setattr(sop_quality_runner, "AgentFactory", FakeAgentFactory)

    result = await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
        session_repository=session_repository,
    )

    assert result["status"] == "succeeded"
    call = build_calls[0]
    assert isinstance(call["agent_factory"], FakeAgentFactory)
    assert call["agent_factory"].repository is llm_provider_repository
    assert isinstance(call["sop_client"], FakeSopClient)
    assert call["submit_quality_result"] is fake_submit_quality_result


@pytest.mark.asyncio
async def test_runner_publishes_session_messages_and_deltas_to_session_broadcast(
    monkeypatch,
) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    session_repository = FakeSessionRepository()
    session_broadcast = FakeSessionBroadcast()
    llm_provider_repository = FakeLlmProviderRepository()

    def fake_build_sop_quality_graph(**kwargs):
        return RuntimePublishingGraph(kwargs)

    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        fake_build_sop_quality_graph,
    )

    await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
        session_repository=session_repository,
        session_broadcast=session_broadcast,
    )

    assert session_broadcast.messages[0][0] == check.session_id
    assert session_broadcast.messages[0][1]["type"] == "message"
    assert session_broadcast.messages[0][1]["content"] == "final review"
    assert session_broadcast.messages[1][1]["type"] == "message_delta"
    assert session_broadcast.messages[1][1]["content"] == "partial"


@pytest.mark.asyncio
async def test_runner_marks_session_completed_on_success(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    session_repository = FakeSessionRepository()
    llm_provider_repository = FakeLlmProviderRepository()

    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        lambda **kwargs: FakeGraph(),
    )

    await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
        session_repository=session_repository,
    )

    assert session_repository.statuses[-1] == (check.session_id, "completed")


@pytest.mark.asyncio
async def test_runner_broadcasts_live_graph_events_to_session_broadcast(
    monkeypatch,
) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    session_broadcast = FakeSessionBroadcast()
    llm_provider_repository = FakeLlmProviderRepository()

    class LiveGraph(FakeGraph):
        async def ainvoke(self, initial_state, *, config):
            await build_calls[0]["live_event_publisher"](
                {
                    "type": "messages",
                    "node": "review_sop",
                    "message": "Streaming",
                }
            )
            return await super().ainvoke(initial_state, config=config)

    build_calls: list[dict] = []

    def fake_build_sop_quality_graph(**kwargs):
        build_calls.append(kwargs)
        return LiveGraph()

    monkeypatch.setattr(
        sop_quality_runner,
        "build_sop_quality_graph",
        fake_build_sop_quality_graph,
    )

    await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
        session_broadcast=session_broadcast,
    )

    _, live_message = next(
        item for item in session_broadcast.messages if item[1]["type"] == "messages"
    )
    assert live_message["session_id"] == check.session_id
    assert live_message["node"] == "review_sop"
    assert live_message["message"] == "Streaming"


@pytest.mark.asyncio
async def test_runner_marks_failed_when_graph_build_fails(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    llm_provider_repository = FakeLlmProviderRepository()

    def fail_build(**kwargs):
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr(sop_quality_runner, "build_sop_quality_graph", fail_build)

    result = await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
    )

    assert result["status"] == "failed"
    assert repository.terminal["status"] == "failed"
    assert repository.terminal["error"]["message"] == "graph unavailable"
    assert repository.events[-1]["event_type"] == "failed"


@pytest.mark.asyncio
async def test_runner_marks_session_failed_when_graph_fails(monkeypatch) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)
    session_repository = FakeSessionRepository()
    llm_provider_repository = FakeLlmProviderRepository()

    def fail_build(**kwargs):
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr(sop_quality_runner, "build_sop_quality_graph", fail_build)

    result = await run_sop_quality_check(
        check.id,
        repository,
        checkpointer=None,
        llm_provider_repository=llm_provider_repository,
        sop_client=FakeSopClient(),
        submit_quality_result=fake_submit_quality_result,
        session_repository=session_repository,
    )

    assert result["status"] == "failed"
    assert session_repository.statuses[-1] == (check.session_id, "failed")


@pytest.mark.asyncio
async def test_new_session_runner_marks_failed_when_checkpoint_setup_fails(
    monkeypatch,
) -> None:
    check = FakeCheck()
    repository = FakeRepository(check)

    monkeypatch.setattr(sop_quality_runner, "async_session", lambda: FakeSessionContext())
    monkeypatch.setattr(
        sop_quality_runner,
        "SopQualityCheckRepository",
        lambda session: repository,
    )
    monkeypatch.setattr(
        sop_quality_runner,
        "SessionRepository",
        lambda session: FakeSessionRepository(),
    )
    monkeypatch.setattr(
        sop_quality_runner,
        "open_postgres_checkpointer",
        lambda *, setup: FailingCheckpointerContext(),
    )

    result = await sop_quality_runner.run_sop_quality_check_with_new_session(check.id)

    assert result["status"] == "failed"
    assert repository.terminal["status"] == "failed"
    assert repository.terminal["error"]["message"] == "checkpoint setup failed"

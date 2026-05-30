from uuid import uuid4

import pytest


class FakeDraftAgent:
    def __init__(self) -> None:
        self.id = uuid4()
        self.enabled = True
        self.draft_config = {
            "system_prompt": "你是谨慎的评审助手。",
            "model": "openai:gpt-5-mini",
            "provider_id": None,
            "model_config": {"temperature": 0},
            "tool_allowlist": [],
            "mcp_server_ids": [],
        }
        self.deleted_at = None


class FakeAgentRepository:
    def __init__(self, agents):
        self._agents = {a.id: a for a in agents}

    async def get_agent(self, agent_id, *, include_deleted: bool = False):
        return self._agents.get(agent_id)


class FakeMessage:
    def __init__(self, *, sequence: int, role: str, content: str, additional_kwargs=None):
        self.sequence = sequence
        self.role = role
        self.content = content
        self.additional_kwargs = additional_kwargs or {}


class FakeSession:
    def __init__(self, sid: int) -> None:
        self.id = sid
        self.status = "active"


class FakeSessionRepository:
    def __init__(self, *, messages=None) -> None:
        self.sessions: dict[int, FakeSession] = {}
        self._messages: dict[int, list[FakeMessage]] = {}
        if messages is not None:
            for sid, msgs in messages.items():
                self._messages[sid] = list(msgs)
        self.statuses: list[tuple[int, str]] = []
        self.appended: list[FakeMessage] = []

    async def get_session(self, session_id: int):
        return self.sessions.get(session_id) or FakeSession(session_id)

    async def get_messages_after(self, session_id: int, after: int = 0, limit: int = 100):
        msgs = self._messages.get(session_id, [])
        return [m for m in msgs if m.sequence > after][:limit]

    async def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        additional_kwargs=None,
    ):
        msgs = self._messages.setdefault(session_id, [])
        seq = (max((m.sequence for m in msgs), default=0)) + 1
        msg = FakeMessage(
            sequence=seq,
            role=role,
            content=content,
            additional_kwargs=additional_kwargs,
        )
        msgs.append(msg)
        self.appended.append(msg)
        return msg

    async def set_status(self, session_id: int, status: str):
        self.statuses.append((session_id, status))
        sess = self.sessions.setdefault(session_id, FakeSession(session_id))
        sess.status = status
        return sess


class FakeBroadcast:
    def __init__(self) -> None:
        self.events: list[tuple[int, dict]] = []

    async def publish(self, session_id: int, message: dict) -> None:
        self.events.append((session_id, dict(message)))


class FakeRuntime:
    def __init__(self, *, output=None, error=None) -> None:
        self.calls: list[dict] = []
        self.output = output or {"messages": [{"role": "assistant", "content": "ok"}]}
        self.error = error
        self.last_version = None
        self.last_messages = None

    async def run(self, *, version, messages):
        self.last_version = version
        self.last_messages = messages
        self.calls.append({"version": version, "messages": messages})
        if self.error is not None:
            raise self.error
        from app.core.agent_runtime import AgentRuntimeResult

        return AgentRuntimeResult(
            messages=self.output["messages"],
            raw_output=self.output,
        )


@pytest.mark.asyncio
async def test_run_draft_turn_runs_runtime_and_persists_assistant_message():
    from app.services.agent_runs import AgentRunService

    agent = FakeDraftAgent()
    agent_repo = FakeAgentRepository([agent])
    session_repo = FakeSessionRepository(
        messages={
            7: [
                FakeMessage(
                    sequence=1,
                    role="user",
                    content="你好",
                    additional_kwargs={"agent_id": str(agent.id)},
                )
            ]
        }
    )
    broadcast = FakeBroadcast()
    runtime = FakeRuntime(
        output={"messages": [{"role": "assistant", "content": "你好,我可以帮你"}]}
    )
    commit_count = 0

    def commit() -> None:
        nonlocal commit_count
        commit_count += 1

    service = AgentRunService(
        agent_repository=agent_repo,
        session_repository=session_repo,
        session_broadcast=broadcast,
        runtime=runtime,
        commit=commit,
    )

    await service.run_draft_turn(agent_id=agent.id, session_id=7)

    assert runtime.calls
    history = runtime.calls[0]["messages"]
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "你好"
    # assistant message must be persisted
    assistant_messages = [m for m in session_repo.appended if m.role == "assistant"]
    assert assistant_messages
    assert assistant_messages[0].content == "你好,我可以帮你"
    # session status set to completed
    assert ("completed",) in [(s[1],) for s in session_repo.statuses]
    assert commit_count >= 1


@pytest.mark.asyncio
async def test_run_draft_turn_marks_failed_when_runtime_errors():
    from app.services.agent_runs import AgentRunService

    agent = FakeDraftAgent()
    agent_repo = FakeAgentRepository([agent])
    session_repo = FakeSessionRepository(
        messages={
            7: [
                FakeMessage(
                    sequence=1,
                    role="user",
                    content="你好",
                    additional_kwargs={"agent_id": str(agent.id)},
                )
            ]
        }
    )
    broadcast = FakeBroadcast()
    runtime = FakeRuntime(error=RuntimeError("boom"))

    service = AgentRunService(
        agent_repository=agent_repo,
        session_repository=session_repo,
        session_broadcast=broadcast,
        runtime=runtime,
        commit=lambda: None,
    )

    await service.run_draft_turn(agent_id=agent.id, session_id=7)

    assert ("failed",) in [(s[1],) for s in session_repo.statuses]
    # broadcast should publish a failure event
    assert any(
        event[1].get("type") == "session_failed" for event in broadcast.events
    )

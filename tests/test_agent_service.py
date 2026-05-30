import pytest
from uuid import uuid4

from app.schemas.agents import (
    AgentCreate,
    AgentDraftConfig,
    AgentDraftUpdate,
    AgentSessionStart,
)


def service_type():
    try:
        from app.services.agents import AgentService
    except ModuleNotFoundError as exc:
        pytest.fail(f"Agent service module is missing: {exc}")
    return AgentService


def draft_config() -> AgentDraftConfig:
    return AgentDraftConfig(
        system_prompt="你是谨慎的评审助手。",
        model="openai:gpt-5-mini",
        model_config={"temperature": 0},
        tool_allowlist=["search_sop"],
        mcp_server_ids=["change-docs"],
    )


class FakeRepository:
    def __init__(self) -> None:
        self.created_kwargs: dict[str, object] | None = None
        self.updated_id = None
        self.updated_kwargs: dict[str, object] | None = None
        self.published_id = None
        self.deleted_id = None
        self.created_agent = object()
        self.updated_agent = object()
        self.published_version = object()
        self.deleted_agent = object()

    async def create_agent(self, **kwargs):
        self.created_kwargs = kwargs
        return self.created_agent

    async def update_draft(self, agent_id, **kwargs):
        self.updated_id = agent_id
        self.updated_kwargs = kwargs
        return self.updated_agent

    async def publish_agent(self, agent_id):
        self.published_id = agent_id
        return self.published_version

    async def soft_delete(self, agent_id):
        self.deleted_id = agent_id
        return self.deleted_agent


@pytest.mark.asyncio
async def test_create_agent_delegates_request_fields_and_commits() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_count = 0

    def commit() -> None:
        nonlocal commit_count
        commit_count += 1

    service = AgentService(repository=repository, commit=commit)
    request = AgentCreate(
        display_name="Release Reviewer",
        description="Checks release quality",
        draft=draft_config(),
    )

    result = await service.create_agent(request)

    assert result is repository.created_agent
    assert repository.created_kwargs == {
        "display_name": "Release Reviewer",
        "description": "Checks release quality",
        "draft": request.draft,
    }
    assert commit_count == 1


@pytest.mark.asyncio
async def test_update_draft_omits_unset_description_from_repository_call() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    service = AgentService(repository=repository)
    agent_id = uuid4()

    result = await service.update_draft(
        agent_id,
        AgentDraftUpdate(display_name="Renamed Reviewer"),
    )

    assert result is repository.updated_agent
    assert repository.updated_id == agent_id
    assert repository.updated_kwargs == {"display_name": "Renamed Reviewer"}


@pytest.mark.asyncio
async def test_update_draft_passes_explicit_null_description_to_repository() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    service = AgentService(repository=repository)
    agent_id = uuid4()

    await service.update_draft(
        agent_id,
        AgentDraftUpdate(description=None),
    )

    assert repository.updated_kwargs == {"description": None}


@pytest.mark.asyncio
async def test_update_draft_awaits_async_commit() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_steps: list[str] = []

    async def commit() -> None:
        commit_steps.append("committed")

    service = AgentService(repository=repository, commit=commit)
    agent_id = uuid4()

    await service.update_draft(
        agent_id,
        AgentDraftUpdate(enabled=False),
    )

    assert repository.updated_kwargs == {"enabled": False}
    assert commit_steps == ["committed"]


@pytest.mark.asyncio
async def test_publish_agent_delegates_and_commits() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_count = 0

    def commit() -> None:
        nonlocal commit_count
        commit_count += 1

    service = AgentService(repository=repository, commit=commit)
    agent_id = uuid4()

    result = await service.publish_agent(agent_id)

    assert result is repository.published_version
    assert repository.published_id == agent_id
    assert commit_count == 1


@pytest.mark.asyncio
async def test_delete_agent_delegates_and_commits() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_count = 0

    def commit() -> None:
        nonlocal commit_count
        commit_count += 1

    service = AgentService(repository=repository, commit=commit)
    agent_id = uuid4()

    result = await service.delete_agent(agent_id)

    assert result is repository.deleted_agent
    assert repository.deleted_id == agent_id
    assert commit_count == 1


class FakeAgentWithDraft:
    def __init__(
        self,
        *,
        agent_id=None,
        enabled: bool = True,
        draft_config: dict | None = None,
    ) -> None:
        self.id = agent_id or uuid4()
        self.enabled = enabled
        self.draft_config = (
            draft_config
            if draft_config is not None
            else draft_config_default()
        )
        self.deleted_at = None


def draft_config_default() -> dict:
    return {
        "system_prompt": "你是谨慎的评审助手。",
        "model": "openai:gpt-5-mini",
        "provider_id": None,
        "model_config": {"temperature": 0},
        "tool_allowlist": [],
        "mcp_server_ids": [],
    }


class FakeAgentRepositoryForSession:
    def __init__(self, agents: list[FakeAgentWithDraft] | None = None) -> None:
        self._agents = {agent.id: agent for agent in (agents or [])}

    async def get_agent(self, agent_id, *, include_deleted: bool = False):
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        return agent


class FakeSessionRepository:
    def __init__(self) -> None:
        self.created_sessions: list[object] = []
        self.appended: list[dict] = []
        self.next_session_id = 123
        self.existing_messages: dict[int, list[object]] = {}
        self.statuses: dict[int, str] = {}

    async def create_session(self, title=None, thread_id=None):
        class _Session:
            def __init__(self, sid):
                self.id = sid
                self.thread_id = thread_id or f"thread-{sid}"

        session = _Session(self.next_session_id)
        self.created_sessions.append(session)
        self.next_session_id += 1
        return session

    async def get_session(self, session_id: int):
        for session in self.created_sessions:
            if session.id == session_id:
                return session
        return None

    async def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        additional_kwargs=None,
    ):
        record = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "additional_kwargs": additional_kwargs or {},
        }
        self.appended.append(record)
        return record

    async def get_messages_after(self, session_id: int, after: int = 0, limit: int = 100):
        return list(self.existing_messages.get(session_id, []))

    async def set_status(self, session_id: int, status: str):
        self.statuses[session_id] = status
        return await self.get_session(session_id)


class FakeBroadcast:
    async def publish_message(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_start_draft_session_creates_session_and_returns_stream_url():
    AgentService = service_type()
    agent_repo = FakeAgentRepositoryForSession()
    agent = FakeAgentWithDraft()
    agent_repo._agents[agent.id] = agent
    session_repo = FakeSessionRepository()
    scheduled: list[tuple] = []

    service = AgentService(
        repository=agent_repo,
        commit=lambda: None,
        session_repository=session_repo,
        session_broadcast=FakeBroadcast(),
        schedule_agent_run=lambda sid, aid: scheduled.append((sid, aid)),
    )

    result = await service.start_draft_session(
        agent.id,
        AgentSessionStart(message="你好"),
    )

    assert result.session_id == 123
    assert result.stream_url == "/api/sessions/123/stream?after=0"
    assert session_repo.appended[0]["role"] == "user"
    assert session_repo.appended[0]["content"] == "你好"
    assert session_repo.appended[0]["additional_kwargs"]["agent_id"] == str(agent.id)
    assert session_repo.statuses[123] == "active"
    assert scheduled == [(123, agent.id)]


@pytest.mark.asyncio
async def test_start_draft_session_rejects_disabled_agent():
    from app.repositories.agents import AgentDisabledError

    AgentService = service_type()
    agent = FakeAgentWithDraft(enabled=False)
    agent_repo = FakeAgentRepositoryForSession([agent])
    session_repo = FakeSessionRepository()

    service = AgentService(
        repository=agent_repo,
        commit=lambda: None,
        session_repository=session_repo,
        session_broadcast=FakeBroadcast(),
    )

    with pytest.raises(AgentDisabledError):
        await service.start_draft_session(
            agent.id,
            AgentSessionStart(message="你好"),
        )


@pytest.mark.asyncio
async def test_start_draft_session_rejects_missing_draft():
    from app.repositories.agents import AgentDraftInvalidError

    AgentService = service_type()
    agent = FakeAgentWithDraft(draft_config={})
    agent_repo = FakeAgentRepositoryForSession([agent])
    session_repo = FakeSessionRepository()

    service = AgentService(
        repository=agent_repo,
        commit=lambda: None,
        session_repository=session_repo,
        session_broadcast=FakeBroadcast(),
    )

    with pytest.raises(AgentDraftInvalidError):
        await service.start_draft_session(
            agent.id,
            AgentSessionStart(message="你好"),
        )

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api import deps
from app.core.database import get_session
from app.main import app
from app.repositories.agents import AgentDisabledError, AgentVersionNotFoundError
from app.repositories.runs import RunRepository
from app.schemas.agents import AgentTestRunCreate
from app.schemas.runs import RunStatus
from app.services.agents import AgentService, run_agent_test_with_new_session


BASE_TIME = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flushes = 0
        self.commits = 0

    def add(self, instance) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


class FakeVersion:
    def __init__(
        self,
        *,
        agent_id=None,
        version_number: int = 1,
        provider_id=None,
    ) -> None:
        self.id = uuid4()
        self.agent_id = agent_id or uuid4()
        self.version_number = version_number
        self.system_prompt = "You are careful."
        self.provider_id = provider_id or uuid4()
        self.model_config = {"temperature": 0}
        self.tool_allowlist = ["search_sop"]
        self.mcp_server_ids = ["change-docs"]
        self.published_at = BASE_TIME


class FakeAgent:
    def __init__(
        self,
        *,
        key: str = "release-reviewer",
        enabled: bool = True,
        latest_version: FakeVersion | None = None,
    ) -> None:
        self.id = uuid4()
        self.key = key
        self.enabled = enabled
        self.latest_version = latest_version
        if latest_version is not None:
            latest_version.agent_id = self.id


class FakeAgentRepository:
    def __init__(
        self,
        *,
        agent: FakeAgent | None,
        versions: list[FakeVersion] | None = None,
        order: list[str] | None = None,
    ) -> None:
        self.agent = agent
        self.versions = versions or []
        self.order = order
        self.number_lookup: tuple[str, int] | None = None
        self.id_lookup = None

    async def get_agent(self, key: str):
        if self.order is not None:
            self.order.append("get_agent")
        if self.agent is None or self.agent.key != key:
            return None
        return self.agent

    async def get_version_by_number(self, key: str, version_number: int):
        self.number_lookup = (key, version_number)
        for version in self.versions:
            if version.version_number == version_number:
                return version
        return None

    async def get_version_by_id(self, version_id):
        self.id_lookup = version_id
        for version in self.versions:
            if version.id == version_id:
                return version
        return None


class FakeRun:
    def __init__(self) -> None:
        self.id = uuid4()
        self.status = RunStatus.pending.value


class FakeRunRepository:
    def __init__(self, order: list[str] | None = None) -> None:
        self.order = order
        self.created_kwargs: dict[str, object] | None = None
        self.run = FakeRun()

    async def create_agent_test_run(self, **kwargs):
        if self.order is not None:
            self.order.append("create_run")
        self.created_kwargs = kwargs
        return self.run


@pytest.fixture(autouse=True)
def clear_app_state():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    for attr in ("agent_test_run_executor", "scheduled_agent_test_run_ids"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


def make_session_override(session: FakeSession):
    async def override_session():
        yield session

    return override_session


@pytest.mark.asyncio
async def test_create_agent_test_run_persists_agent_test_payload() -> None:
    session = FakeSession()
    repository = RunRepository(session)
    version = FakeVersion(version_number=7)
    messages = [{"role": "user", "content": "Can this deploy?"}]

    run = await repository.create_agent_test_run(
        agent_key="release-reviewer",
        agent_version=version,
        messages=messages,
        input_preview="Can this deploy?",
        created_by="qa@example.com",
    )

    assert session.added == [run]
    assert session.flushes == 1
    assert run.assistant_id == "react-agent-test-v1"
    assert run.subject_type == "agent_test"
    assert run.subject_id == "release-reviewer"
    assert run.env_key is None
    assert run.status == RunStatus.pending.value
    assert run.active_conflict_key is None
    assert run.metadata_ == {
        "subject_type": "agent_test",
        "subject_id": "release-reviewer",
        "agent_id": str(version.agent_id),
        "agent_key": "release-reviewer",
        "agent_version_id": str(version.id),
        "agent_version_number": 7,
        "run_kind": "agent_test",
        "input_preview": "Can this deploy?",
    }
    assert run.kwargs == {
        "agent_key": "release-reviewer",
        "agent_version_id": str(version.id),
        "agent_version_number": 7,
    }
    assert run.completed_nodes == []
    assert run.subject_snapshot == {
        "messages": messages,
        "agent_version": {
            "id": str(version.id),
            "version_number": 7,
            "provider_id": str(version.provider_id),
            "tool_allowlist": ["search_sop"],
            "mcp_server_ids": ["change-docs"],
        },
    }
    assert run.created_by == "qa@example.com"


@pytest.mark.asyncio
async def test_create_agent_test_run_snapshots_provider_id() -> None:
    provider_id = uuid4()
    session = FakeSession()
    repository = RunRepository(session)
    version = FakeVersion(provider_id=provider_id)

    run = await repository.create_agent_test_run(
        agent_key="release-reviewer",
        agent_version=version,
        messages=[{"role": "user", "content": "Can this deploy?"}],
        input_preview="Can this deploy?",
    )

    assert run.subject_snapshot["agent_version"]["provider_id"] == str(provider_id)
    assert "model" not in run.subject_snapshot["agent_version"]


@pytest.mark.asyncio
async def test_start_test_run_uses_latest_version_and_schedules_after_commit() -> None:
    order: list[str] = []
    version = FakeVersion(version_number=3)
    agent = FakeAgent(latest_version=version)
    agent_repository = FakeAgentRepository(agent=agent, versions=[version], order=order)
    run_repository = FakeRunRepository(order=order)

    async def commit() -> None:
        order.append("commit")

    def schedule(run_id) -> None:
        order.append("schedule")
        assert order[-2] == "commit"
        assert run_id == run_repository.run.id

    service = AgentService(
        repository=agent_repository,
        run_repository=run_repository,
        schedule_test_run=schedule,
        commit=commit,
    )

    result = await service.start_test_run(
        "release-reviewer",
        AgentTestRunCreate(messages=[{"role": "user", "content": "Can this deploy?"}]),
    )

    assert order == ["get_agent", "create_run", "commit", "schedule"]
    assert result.run_id == run_repository.run.id
    assert result.status == RunStatus.pending
    assert result.status_url == f"/api/runs/{run_repository.run.id}"
    assert result.events_url == f"/api/runs/{run_repository.run.id}/events"
    assert run_repository.created_kwargs is not None
    assert run_repository.created_kwargs["agent_key"] == "release-reviewer"
    assert run_repository.created_kwargs["agent_version"] is version
    assert run_repository.created_kwargs["messages"] == [
        {"role": "user", "content": "Can this deploy?"}
    ]


@pytest.mark.asyncio
async def test_start_test_run_resolves_explicit_version_number() -> None:
    agent = FakeAgent()
    old_version = FakeVersion(agent_id=agent.id, version_number=1)
    latest_version = FakeVersion(agent_id=agent.id, version_number=2)
    agent.latest_version = latest_version
    agent_repository = FakeAgentRepository(
        agent=agent,
        versions=[old_version, latest_version],
    )
    run_repository = FakeRunRepository()
    service = AgentService(
        repository=agent_repository,
        run_repository=run_repository,
    )

    await service.start_test_run(
        "release-reviewer",
        AgentTestRunCreate(
            version_number=1,
            messages=[{"role": "user", "content": "Use v1."}],
        ),
    )

    assert agent_repository.number_lookup == ("release-reviewer", 1)
    assert run_repository.created_kwargs is not None
    assert run_repository.created_kwargs["agent_version"] is old_version


@pytest.mark.asyncio
async def test_start_test_run_resolves_explicit_version_id() -> None:
    agent = FakeAgent()
    version = FakeVersion(agent_id=agent.id, version_number=4)
    agent.latest_version = version
    agent_repository = FakeAgentRepository(agent=agent, versions=[version])
    run_repository = FakeRunRepository()
    service = AgentService(
        repository=agent_repository,
        run_repository=run_repository,
    )

    await service.start_test_run(
        "release-reviewer",
        AgentTestRunCreate(
            version_id=version.id,
            messages=[{"role": "user", "content": "Use this version."}],
        ),
    )

    assert agent_repository.id_lookup == version.id
    assert run_repository.created_kwargs is not None
    assert run_repository.created_kwargs["agent_version"] is version


@pytest.mark.asyncio
async def test_start_test_run_raises_when_no_version_exists() -> None:
    agent = FakeAgent(latest_version=None)
    agent_repository = FakeAgentRepository(agent=agent)
    run_repository = FakeRunRepository()
    session = FakeSession()
    service = AgentService(
        repository=agent_repository,
        run_repository=run_repository,
        commit=session.commit,
    )

    with pytest.raises(AgentVersionNotFoundError):
        await service.start_test_run(
            "release-reviewer",
            AgentTestRunCreate(
                messages=[{"role": "user", "content": "Can this deploy?"}],
            ),
        )

    assert run_repository.created_kwargs is None
    assert session.commits == 0


@pytest.mark.asyncio
async def test_start_test_run_raises_when_agent_is_disabled() -> None:
    version = FakeVersion(version_number=3)
    agent = FakeAgent(enabled=False, latest_version=version)
    agent_repository = FakeAgentRepository(agent=agent, versions=[version])
    run_repository = FakeRunRepository()
    session = FakeSession()
    service = AgentService(
        repository=agent_repository,
        run_repository=run_repository,
        commit=session.commit,
    )

    with pytest.raises(AgentDisabledError):
        await service.start_test_run(
            "release-reviewer",
            AgentTestRunCreate(
                messages=[{"role": "user", "content": "Can this deploy?"}],
            ),
        )

    assert run_repository.created_kwargs is None
    assert session.commits == 0


@pytest.mark.asyncio
async def test_start_agent_test_run_endpoint_returns_accepted_and_schedules() -> None:
    version = FakeVersion(version_number=5)
    agent = FakeAgent(latest_version=version)
    agent_repository = FakeAgentRepository(agent=agent, versions=[version])
    run_repository = FakeRunRepository()
    session = FakeSession()
    app.dependency_overrides[get_session] = make_session_override(session)
    app.dependency_overrides[deps.get_agent_repository] = lambda: agent_repository
    app.dependency_overrides[deps.get_run_repository] = lambda: run_repository
    app.state.scheduled_agent_test_run_ids = []

    async def fake_executor(run_id) -> None:
        app.state.scheduled_agent_test_run_ids.append(str(run_id))

    app.state.agent_test_run_executor = fake_executor

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/agents/release-reviewer/test-runs",
            json={"messages": [{"role": "user", "content": "Can this deploy?"}]},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["status_url"] == f"/api/runs/{body['run_id']}"
    assert body["events_url"] == f"/api/runs/{body['run_id']}/events"
    assert session.commits == 1
    assert app.state.scheduled_agent_test_run_ids == [body["run_id"]]
    assert run_repository.created_kwargs is not None
    assert run_repository.created_kwargs["messages"] == [
        {"role": "user", "content": "Can this deploy?"}
    ]


@pytest.mark.asyncio
async def test_start_agent_test_run_endpoint_returns_400_when_agent_disabled() -> None:
    version = FakeVersion(version_number=5)
    agent = FakeAgent(enabled=False, latest_version=version)
    agent_repository = FakeAgentRepository(agent=agent, versions=[version])
    run_repository = FakeRunRepository()
    session = FakeSession()
    app.dependency_overrides[get_session] = make_session_override(session)
    app.dependency_overrides[deps.get_agent_repository] = lambda: agent_repository
    app.dependency_overrides[deps.get_run_repository] = lambda: run_repository

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/agents/release-reviewer/test-runs",
            json={"messages": [{"role": "user", "content": "Can this deploy?"}]},
        )

    assert response.status_code == 400
    assert run_repository.created_kwargs is None
    assert session.commits == 0


def test_default_agent_test_executor_is_available() -> None:
    assert callable(run_agent_test_with_new_session)

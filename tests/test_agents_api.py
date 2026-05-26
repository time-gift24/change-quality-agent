from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from app.api import deps
from app.core.database import get_session
from app.main import app
from app.repositories.agents import (
    AgentDraftInvalidError,
    AgentKeyExistsError,
    AgentNotFoundError,
)
from app.schemas.agents import AgentDraftConfig


BASE_TIME = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeVersion:
    def __init__(
        self,
        *,
        agent_id,
        version_number: int = 1,
        published_at: datetime = BASE_TIME,
    ) -> None:
        self.id = uuid4()
        self.agent_id = agent_id
        self.version_number = version_number
        self.system_prompt = "You are careful."
        self.model = "openai:gpt-5-mini"
        self.model_config = {"temperature": 0}
        self.tool_allowlist = ["search_sop"]
        self.mcp_server_ids = ["change-docs"]
        self.published_by = "ops@example.com"
        self.published_at = published_at


class FakeAgent:
    def __init__(
        self,
        *,
        key: str = "release-reviewer",
        display_name: str = "Release Reviewer",
        description: str | None = "Checks release quality",
        draft_config: dict[str, object] | None = None,
    ) -> None:
        self.id = uuid4()
        self.key = key
        self.display_name = display_name
        self.description = description
        self.enabled = True
        self.draft_config = draft_config or draft_payload()
        self.latest_version = None
        self.created_at = BASE_TIME
        self.updated_at = BASE_TIME
        self.deleted_at = None


class FakeAgentRepository:
    def __init__(
        self,
        *,
        agents: list[FakeAgent] | None = None,
        duplicate_key: str | None = None,
        invalid_publish_key: str | None = None,
    ) -> None:
        self.agents = {agent.key: agent for agent in agents or []}
        self.versions: dict[str, list[FakeVersion]] = {key: [] for key in self.agents}
        self.duplicate_key = duplicate_key
        self.invalid_publish_key = invalid_publish_key
        self.list_include_deleted: list[bool] = []
        self.updated_key: str | None = None
        self.updated_kwargs: dict[str, object] | None = None
        self.deleted_key: str | None = None

    async def create_agent(self, **kwargs):
        key = kwargs["key"]
        if key == self.duplicate_key:
            raise AgentKeyExistsError(key)
        agent = FakeAgent(
            key=key,
            display_name=kwargs["display_name"],
            description=kwargs["description"],
            draft_config=to_draft_payload(kwargs["draft"]),
        )
        self.agents[key] = agent
        self.versions[key] = []
        return agent

    async def list_agents(self, *, include_deleted: bool = False):
        self.list_include_deleted.append(include_deleted)
        agents = list(self.agents.values())
        if not include_deleted:
            agents = [agent for agent in agents if agent.deleted_at is None]
        return agents

    async def get_agent(self, key: str, *, include_deleted: bool = False):
        agent = self.agents.get(key)
        if agent is None:
            return None
        if agent.deleted_at is not None and not include_deleted:
            return None
        return agent

    async def update_draft(self, key: str, **kwargs):
        agent = self.agents.get(key)
        if agent is None:
            raise AgentNotFoundError(key)
        self.updated_key = key
        self.updated_kwargs = kwargs
        if "display_name" in kwargs:
            agent.display_name = kwargs["display_name"]
        if "description" in kwargs:
            agent.description = kwargs["description"]
        if "enabled" in kwargs:
            agent.enabled = kwargs["enabled"]
        if "draft" in kwargs:
            agent.draft_config = to_draft_payload(kwargs["draft"])
        return agent

    async def publish_agent(self, key: str):
        agent = self.agents.get(key)
        if agent is None:
            raise AgentNotFoundError(key)
        if key == self.invalid_publish_key:
            raise AgentDraftInvalidError(key)
        version = FakeVersion(
            agent_id=agent.id,
            version_number=len(self.versions.setdefault(key, [])) + 1,
        )
        self.versions[key].append(version)
        agent.latest_version = version
        return version

    async def list_versions(self, key: str):
        return sorted(
            self.versions.get(key, []),
            key=lambda version: version.version_number,
            reverse=True,
        )

    async def get_version_by_number(self, key: str, version_number: int):
        for version in self.versions.get(key, []):
            if version.version_number == version_number:
                return version
        return None

    async def soft_delete(self, key: str):
        agent = self.agents.get(key)
        if agent is None:
            raise AgentNotFoundError(key)
        self.deleted_key = key
        agent.deleted_at = BASE_TIME + timedelta(minutes=5)
        return agent


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def draft_payload() -> dict[str, object]:
    return {
        "system_prompt": "You are careful.",
        "model": "openai:gpt-5-mini",
        "model_config": {"temperature": 0},
        "tool_allowlist": ["search_sop"],
        "mcp_server_ids": ["change-docs"],
    }


def to_draft_payload(draft: object) -> dict[str, object]:
    if isinstance(draft, AgentDraftConfig):
        return draft.model_dump(mode="json")
    return dict(draft)


def create_payload(key: str = "release-reviewer") -> dict[str, object]:
    return {
        "key": key,
        "display_name": "Release Reviewer",
        "description": "Checks release quality",
        "draft": draft_payload(),
    }


def make_session_override(session: FakeSession):
    async def override_session():
        yield session

    return override_session


def override_dependencies(repository: FakeAgentRepository, session: FakeSession):
    app.dependency_overrides[get_session] = make_session_override(session)
    get_agent_repository = getattr(deps, "get_agent_repository", None)
    if get_agent_repository is not None:
        app.dependency_overrides[get_agent_repository] = lambda: repository


@pytest.mark.asyncio
async def test_create_agent_returns_detail_and_commits() -> None:
    repository = FakeAgentRepository()
    session = FakeSession()
    override_dependencies(repository, session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/agents", json=create_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "release-reviewer"
    assert body["has_draft"] is True
    assert body["draft"]["model_config"] == {"temperature": 0}
    assert body["latest_version"] is None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_create_agent_returns_409_when_key_exists() -> None:
    repository = FakeAgentRepository(duplicate_key="release-reviewer")
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/agents", json=create_payload())

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_agents_returns_summaries_without_deleted_by_default() -> None:
    active_agent = FakeAgent()
    deleted_agent = FakeAgent(key="deleted-reviewer", display_name="Deleted Reviewer")
    deleted_agent.deleted_at = BASE_TIME
    repository = FakeAgentRepository(agents=[active_agent, deleted_agent])
    version = FakeVersion(agent_id=active_agent.id)
    active_agent.latest_version = version
    repository.versions[active_agent.key].append(version)
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/agents")

    assert response.status_code == 200
    body = response.json()
    assert [agent["key"] for agent in body] == ["release-reviewer"]
    assert body[0]["latest_version"]["version_number"] == 1
    assert "draft" not in body[0]
    assert repository.list_include_deleted == [False]


@pytest.mark.asyncio
async def test_list_agents_can_include_deleted() -> None:
    active_agent = FakeAgent()
    deleted_agent = FakeAgent(key="deleted-reviewer", display_name="Deleted Reviewer")
    deleted_agent.deleted_at = BASE_TIME
    repository = FakeAgentRepository(agents=[active_agent, deleted_agent])
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/agents?include_deleted=true")

    assert response.status_code == 200
    assert [agent["key"] for agent in response.json()] == [
        "release-reviewer",
        "deleted-reviewer",
    ]
    assert repository.list_include_deleted == [True]


@pytest.mark.asyncio
async def test_get_agent_returns_404_when_missing() -> None:
    override_dependencies(FakeAgentRepository(), FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/agents/missing-agent")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_draft_preserves_explicit_body_fields() -> None:
    repository = FakeAgentRepository(agents=[FakeAgent()])
    session = FakeSession()
    override_dependencies(repository, session)
    patch_payload = {
        "description": None,
        "enabled": False,
        "draft": {
            **draft_payload(),
            "system_prompt": "Review only risky changes.",
            "model_config": {"temperature": 0.2},
        },
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            "/api/agents/release-reviewer/draft",
            json=patch_payload,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] is None
    assert body["enabled"] is False
    assert body["draft"]["system_prompt"] == "Review only risky changes."
    assert body["draft"]["model_config"] == {"temperature": 0.2}
    assert repository.updated_key == "release-reviewer"
    assert repository.updated_kwargs is not None
    assert repository.updated_kwargs["description"] is None
    assert repository.updated_kwargs["enabled"] is False
    assert "draft" in repository.updated_kwargs
    assert session.commits == 1


@pytest.mark.asyncio
async def test_publish_agent_returns_created_version_detail() -> None:
    repository = FakeAgentRepository(agents=[FakeAgent()])
    session = FakeSession()
    override_dependencies(repository, session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/agents/release-reviewer/publish")

    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 1
    assert body["model_config"] == {"temperature": 0}
    assert "model_parameters" not in body
    assert session.commits == 1


@pytest.mark.asyncio
async def test_publish_agent_returns_400_for_invalid_draft() -> None:
    repository = FakeAgentRepository(
        agents=[FakeAgent()],
        invalid_publish_key="release-reviewer",
    )
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/agents/release-reviewer/publish")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_versions_returns_descending_summaries() -> None:
    agent = FakeAgent()
    repository = FakeAgentRepository(agents=[agent])
    repository.versions[agent.key] = [
        FakeVersion(agent_id=agent.id, version_number=1, published_at=BASE_TIME),
        FakeVersion(
            agent_id=agent.id,
            version_number=2,
            published_at=BASE_TIME + timedelta(minutes=1),
        ),
    ]
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/agents/release-reviewer/versions")

    assert response.status_code == 200
    assert [version["version_number"] for version in response.json()] == [2, 1]


@pytest.mark.asyncio
async def test_get_version_returns_detail_or_404() -> None:
    agent = FakeAgent()
    repository = FakeAgentRepository(agents=[agent])
    repository.versions[agent.key] = [FakeVersion(agent_id=agent.id, version_number=3)]
    override_dependencies(repository, FakeSession())

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        found = await client.get("/api/agents/release-reviewer/versions/3")
        missing = await client.get("/api/agents/release-reviewer/versions/99")

    assert found.status_code == 200
    assert found.json()["version_number"] == 3
    assert found.json()["model_config"] == {"temperature": 0}
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_returns_no_content_and_commits() -> None:
    repository = FakeAgentRepository(agents=[FakeAgent()])
    session = FakeSession()
    override_dependencies(repository, session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete("/api/agents/release-reviewer")

    assert response.status_code == 204
    assert response.content == b""
    assert repository.deleted_key == "release-reviewer"
    assert session.commits == 1

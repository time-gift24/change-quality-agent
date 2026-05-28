import os
from datetime import UTC, datetime
from inspect import signature
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.agents  # noqa: F401
from app.core.database import Base
from app.schemas.agents import AgentDraftConfig

requires_test_database = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL to run repository integration tests",
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


def repository_types() -> Any:
    try:
        from app.repositories import agents
    except ModuleNotFoundError as exc:
        pytest.fail(f"Agent repository module is missing: {exc}")
    return agents


def test_repository_module_defines_expected_public_api() -> None:
    agents = repository_types()

    assert agents.AgentRepository is not None
    assert agents.UNSET is not None
    assert agents.AgentNotFoundError is not None
    assert agents.AgentDraftInvalidError is not None
    assert agents.AgentVersionNotFoundError is not None


def test_update_draft_uses_public_sentinel_for_optional_fields() -> None:
    agents = repository_types()
    parameters = signature(agents.AgentRepository.update_draft).parameters

    assert parameters["display_name"].default is agents.UNSET
    assert parameters["description"].default is agents.UNSET
    assert parameters["enabled"].default is agents.UNSET
    assert parameters["draft"].default is agents.UNSET


def test_dump_draft_config_uses_external_model_config_key() -> None:
    agents = repository_types()

    payload = agents.dump_draft_config(draft_config(temperature=0.1))

    assert payload["model_config"] == {"temperature": 0.1}
    assert "model_parameters" not in payload


def test_dump_draft_config_rejects_invalid_raw_draft() -> None:
    agents = repository_types()

    with pytest.raises(agents.AgentDraftInvalidError):
        agents.dump_draft_config(
            {
                "system_prompt": "",
                "model": "openai:gpt-5-mini",
                "model_config": {},
            },
        )


def test_dump_draft_config_preserves_provider_id() -> None:
    agents = repository_types()
    provider_id = uuid4()

    payload = agents.dump_draft_config(
        draft_config(model="gpt-5-mini", provider_id=provider_id),
    )

    assert payload["provider_id"] == str(provider_id)
    assert payload["model"] == "gpt-5-mini"


def draft_config(
    *,
    system_prompt: str = "You are careful.",
    model: str = "openai:gpt-5-mini",
    provider_id=None,
    temperature: float = 0,
) -> AgentDraftConfig:
    return AgentDraftConfig(
        system_prompt=system_prompt,
        model=model,
        provider_id=provider_id,
        model_config={"temperature": temperature},
        tool_allowlist=["search_sop"],
        mcp_server_ids=["change-docs"],
    )


class FakeSession:
    def __init__(self) -> None:
        self.flushed = 0

    async def flush(self) -> None:
        self.flushed += 1


class FakeAgent:
    def __init__(
        self,
        *,
        description: str | None = "Initial description",
        deleted_at: datetime | None = None,
    ) -> None:
        self.display_name = "Release Reviewer"
        self.description = description
        self.enabled = True
        self.draft_config = {}
        self.updated_by = None
        self.deleted_at = deleted_at


@pytest.mark.asyncio
async def test_update_draft_returns_reloaded_agent_after_flush() -> None:
    agents = repository_types()
    session = FakeSession()
    initial_agent = FakeAgent()
    reloaded_agent = FakeAgent(description=None)

    class ReloadingRepository(agents.AgentRepository):
        def __init__(self) -> None:
            super().__init__(session)
            self.calls: list[tuple[object, bool, bool, int]] = []

        async def _require_agent(
            self,
            agent_id,
            *,
            include_deleted: bool = False,
            lock: bool = False,
        ) -> FakeAgent:
            self.calls.append((agent_id, include_deleted, lock, session.flushed))
            if session.flushed == 0:
                return initial_agent
            return reloaded_agent

        async def _require_active_agent(
            self,
            agent_id,
            *,
            lock: bool = False,
        ) -> FakeAgent:
            return await self._require_agent(agent_id, lock=lock)

    repository = ReloadingRepository()
    agent_id = uuid4()

    result = await repository.update_draft(agent_id, description=None)

    assert result is reloaded_agent
    assert initial_agent.description is None
    assert session.flushed == 1
    assert repository.calls == [
        (agent_id, False, False, 0),
        (agent_id, False, False, 1),
    ]


@pytest.mark.asyncio
async def test_soft_delete_returns_reloaded_deleted_agent_after_flush() -> None:
    agents = repository_types()
    session = FakeSession()
    initial_agent = FakeAgent()
    reloaded_agent = FakeAgent(deleted_at=datetime(2026, 5, 26, tzinfo=UTC))

    class ReloadingRepository(agents.AgentRepository):
        def __init__(self) -> None:
            super().__init__(session)
            self.calls: list[tuple[object, bool, bool, int]] = []

        async def _require_agent(
            self,
            agent_id,
            *,
            include_deleted: bool = False,
            lock: bool = False,
        ) -> FakeAgent:
            self.calls.append((agent_id, include_deleted, lock, session.flushed))
            if session.flushed == 0:
                return initial_agent
            return reloaded_agent

        async def _require_active_agent(
            self,
            agent_id,
            *,
            lock: bool = False,
        ) -> FakeAgent:
            return await self._require_agent(agent_id, lock=lock)

    repository = ReloadingRepository()
    agent_id = uuid4()

    result = await repository.soft_delete(agent_id)

    assert result is reloaded_agent
    assert initial_agent.deleted_at is not None
    assert session.flushed == 1
    assert repository.calls == [
        (agent_id, False, False, 0),
        (agent_id, True, False, 1),
    ]


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_create_agent_stores_draft_with_external_model_config_key(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)

    agent = await repository.create_agent(
        display_name="Release Reviewer",
        description="Checks release quality",
        draft=draft_config(),
        created_by="ops@example.com",
    )

    assert agent.created_by == "ops@example.com"
    assert agent.draft_config["model_config"] == {"temperature": 0}
    assert "model_parameters" not in agent.draft_config


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_update_draft_updates_only_provided_fields_and_can_clear_description(
    session,
) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    agent = await repository.create_agent(
        display_name="Release Reviewer",
        description="Initial description",
        draft=draft_config(),
    )

    renamed = await repository.update_draft(
        agent.id,
        display_name="Renamed Reviewer",
        enabled=False,
        updated_by="editor@example.com",
    )
    cleared = await repository.update_draft(agent.id, description=None)

    assert renamed.display_name == "Renamed Reviewer"
    assert renamed.enabled is False
    assert renamed.updated_by == "editor@example.com"
    assert renamed.draft_config["model_config"] == {"temperature": 0}
    assert cleared.description is None


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_publish_agent_creates_monotonic_versions_and_eager_loads_latest(
    session,
) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    agent = await repository.create_agent(
        display_name="Release Reviewer",
        description=None,
        draft=draft_config(temperature=0),
    )

    first = await repository.publish_agent(
        agent.id,
        published_by="publisher@example.com",
    )
    await repository.update_draft(
        agent.id,
        draft=draft_config(
            system_prompt="You are more concise.",
            temperature=0.2,
        ),
    )
    second = await repository.publish_agent(agent.id)

    assert first.version_number == 1
    assert first.model_config == {"temperature": 0}
    assert first.published_by == "publisher@example.com"
    assert second.version_number == 2
    assert second.system_prompt == "You are more concise."
    assert second.model_config == {"temperature": 0.2}

    versions = await repository.list_versions(agent.id)
    assert [version.version_number for version in versions] == [2, 1]

    first_by_number = await repository.get_version_by_number(agent.id, 1)
    first_by_id = await repository.get_version_by_id(first.id)
    assert first_by_number.id == first.id
    assert first_by_id.id == first.id

    listed_agents = await repository.list_agents()
    assert "latest_version" not in inspect(listed_agents[0]).unloaded
    assert listed_agents[0].latest_version.version_number == 2


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_publish_agent_copies_provider_id_to_version(session) -> None:
    agents = repository_types()
    from app.repositories.llm_providers import LlmProviderRepository

    provider = await LlmProviderRepository(session).create(
        display_name="OpenAI",
        provider_type="openai",
    )
    repository = agents.AgentRepository(session)
    agent = await repository.create_agent(
        display_name="Release Reviewer",
        description=None,
        draft=draft_config(model="gpt-5-mini", provider_id=provider.id),
    )

    version = await repository.publish_agent(agent.id)

    assert version.model == "gpt-5-mini"
    assert version.provider_id == provider.id


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_publish_agent_rejects_invalid_draft(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    agent = await repository.create_agent(
        display_name="Release Reviewer",
        description=None,
        draft=draft_config(),
    )
    agent.draft_config = {
        "system_prompt": "",
        "model": "openai:gpt-5-mini",
        "model_config": {},
    }
    await session.flush()

    with pytest.raises(agents.AgentDraftInvalidError):
        await repository.publish_agent(agent.id)


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_soft_delete_hides_agent_by_default_and_preserves_versions(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    agent = await repository.create_agent(
        display_name="Release Reviewer",
        description=None,
        draft=draft_config(),
    )
    version = await repository.publish_agent(agent.id)

    deleted = await repository.soft_delete(
        agent.id,
        updated_by="deleter@example.com",
    )

    assert deleted.deleted_at is not None
    assert deleted.updated_by == "deleter@example.com"
    assert await repository.get_agent(agent.id) is None
    assert await repository.list_agents() == []

    deleted_agent = await repository.get_agent(
        agent.id,
        include_deleted=True,
    )
    preserved_version = await repository.get_version_by_id(version.id)
    assert deleted_agent.id == deleted.id
    assert preserved_version.id == version.id


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_update_and_delete_missing_agents_raise_not_found(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)

    with pytest.raises(agents.AgentNotFoundError):
        await repository.update_draft(uuid4(), enabled=False)

    with pytest.raises(agents.AgentNotFoundError):
        await repository.soft_delete(uuid4())

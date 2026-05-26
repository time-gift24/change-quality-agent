import os
from typing import Any

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
    assert agents.AgentKeyExistsError is not None
    assert agents.AgentNotFoundError is not None
    assert agents.AgentDraftInvalidError is not None
    assert agents.AgentVersionNotFoundError is not None


def draft_config(
    *,
    system_prompt: str = "You are careful.",
    model: str = "openai:gpt-5-mini",
    temperature: float = 0,
) -> AgentDraftConfig:
    return AgentDraftConfig(
        system_prompt=system_prompt,
        model=model,
        model_config={"temperature": temperature},
        tool_allowlist=["search_sop"],
        mcp_server_ids=["change-docs"],
    )


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_create_agent_stores_draft_with_external_model_config_key(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)

    agent = await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        description="Checks release quality",
        draft=draft_config(),
        created_by="ops@example.com",
    )

    assert agent.key == "release-reviewer"
    assert agent.created_by == "ops@example.com"
    assert agent.draft_config["model_config"] == {"temperature": 0}
    assert "model_parameters" not in agent.draft_config


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_create_agent_rejects_duplicate_key(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        description=None,
        draft=draft_config(),
    )

    with pytest.raises(agents.AgentKeyExistsError):
        await repository.create_agent(
            key="release-reviewer",
            display_name="Duplicate Reviewer",
            description=None,
            draft=draft_config(),
        )


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_update_draft_updates_only_provided_fields_and_can_clear_description(
    session,
) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        description="Initial description",
        draft=draft_config(),
    )

    renamed = await repository.update_draft(
        "release-reviewer",
        display_name="Renamed Reviewer",
        enabled=False,
        updated_by="editor@example.com",
    )
    cleared = await repository.update_draft("release-reviewer", description=None)

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
    await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        description=None,
        draft=draft_config(temperature=0),
    )

    first = await repository.publish_agent(
        "release-reviewer",
        published_by="publisher@example.com",
    )
    await repository.update_draft(
        "release-reviewer",
        draft=draft_config(
            system_prompt="You are more concise.",
            temperature=0.2,
        ),
    )
    second = await repository.publish_agent("release-reviewer")

    assert first.version_number == 1
    assert first.model_config == {"temperature": 0}
    assert first.published_by == "publisher@example.com"
    assert second.version_number == 2
    assert second.system_prompt == "You are more concise."
    assert second.model_config == {"temperature": 0.2}

    versions = await repository.list_versions("release-reviewer")
    assert [version.version_number for version in versions] == [2, 1]

    first_by_number = await repository.get_version_by_number("release-reviewer", 1)
    first_by_id = await repository.get_version_by_id(first.id)
    assert first_by_number.id == first.id
    assert first_by_id.id == first.id

    listed_agents = await repository.list_agents()
    assert "latest_version" not in inspect(listed_agents[0]).unloaded
    assert listed_agents[0].latest_version.version_number == 2


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_publish_agent_rejects_invalid_draft(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    agent = await repository.create_agent(
        key="release-reviewer",
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
        await repository.publish_agent("release-reviewer")


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_soft_delete_hides_agent_by_default_and_preserves_versions(session) -> None:
    agents = repository_types()
    repository = agents.AgentRepository(session)
    await repository.create_agent(
        key="release-reviewer",
        display_name="Release Reviewer",
        description=None,
        draft=draft_config(),
    )
    version = await repository.publish_agent("release-reviewer")

    deleted = await repository.soft_delete(
        "release-reviewer",
        updated_by="deleter@example.com",
    )

    assert deleted.deleted_at is not None
    assert deleted.updated_by == "deleter@example.com"
    assert await repository.get_agent("release-reviewer") is None
    assert await repository.list_agents() == []

    deleted_agent = await repository.get_agent(
        "release-reviewer",
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
        await repository.update_draft("missing-agent", enabled=False)

    with pytest.raises(agents.AgentNotFoundError):
        await repository.soft_delete("missing-agent")

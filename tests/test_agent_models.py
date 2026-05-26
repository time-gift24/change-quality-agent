from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from app.models.agents import Agent, AgentVersion


def test_agent_table_name() -> None:
    assert Agent.__tablename__ == "agents"


def test_agent_version_table_name() -> None:
    assert AgentVersion.__tablename__ == "agent_versions"


def test_agent_key_has_named_unique_index() -> None:
    indexes = {index.name: index for index in Agent.__table__.indexes}

    key_index = indexes["uq_agents_key"]

    assert key_index.unique is True
    assert [column.name for column in key_index.columns] == ["key"]


def test_agent_version_has_expected_indexes() -> None:
    indexes = {index.name: index for index in AgentVersion.__table__.indexes}

    version_index = indexes["uq_agent_versions_agent_version"]
    published_index = indexes["ix_agent_versions_agent_published"]

    assert version_index.unique is True
    assert [column.name for column in version_index.columns] == [
        "agent_id",
        "version_number",
    ]
    assert [column.name for column in published_index.columns] == [
        "agent_id",
        "published_at",
    ]


def test_agent_relationship_mappers_configure_for_circular_foreign_keys() -> None:
    configure_mappers()

    agent_relationships = inspect(Agent).relationships

    versions = agent_relationships["versions"]
    latest_version = agent_relationships["latest_version"]

    assert (Agent.__table__.c.id, AgentVersion.__table__.c.agent_id) in (
        versions.synchronize_pairs
    )
    assert (AgentVersion.__table__.c.id, Agent.__table__.c.latest_version_id) in (
        latest_version.synchronize_pairs
    )
    assert latest_version.post_update is True

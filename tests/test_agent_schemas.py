from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agents import (
    AgentCreate,
    AgentDraftConfig,
    AgentTestRunCreate,
    AgentVersionDetail,
)


def test_agent_create_accepts_initial_draft() -> None:
    provider_id = uuid4()
    request = AgentCreate(
        key="release-reviewer",
        display_name="Release Reviewer",
        description="Checks release quality",
        draft=AgentDraftConfig(
            system_prompt="You are careful.",
            provider_id=provider_id,
            model_config={"temperature": 0},
            tool_allowlist=["search_sop"],
            mcp_server_ids=["change-docs"],
        ),
    )

    assert request.key == "release-reviewer"
    assert request.draft.provider_id == provider_id


def test_agent_draft_config_requires_provider_id() -> None:
    provider_id = uuid4()

    draft = AgentDraftConfig(
        system_prompt="Review changes.",
        provider_id=provider_id,
        model_config={"temperature": 0},
    )

    assert draft.provider_id == provider_id
    assert draft.model_dump(mode="json")["provider_id"] == str(provider_id)


def test_agent_draft_config_rejects_missing_provider_id() -> None:
    with pytest.raises(ValidationError):
        AgentDraftConfig(system_prompt="Review changes.")


def test_agent_draft_config_rejects_model_field() -> None:
    with pytest.raises(ValidationError):
        AgentDraftConfig(
            system_prompt="Review changes.",
            model="gpt-4.1-mini",
            provider_id=uuid4(),
        )


def test_agent_test_run_requires_messages() -> None:
    request = AgentTestRunCreate(
        messages=[{"role": "user", "content": "Review this change."}]
    )

    assert request.messages[0].role == "user"
    assert request.version_number is None


def test_agent_draft_config_dumps_external_model_config_key() -> None:
    draft = AgentDraftConfig(
        system_prompt="You are careful.",
        provider_id=uuid4(),
        model_config={"temperature": 0},
    )

    payload = draft.model_dump(mode="json")

    assert payload["model_config"] == {"temperature": 0}
    assert "model_parameters" not in payload


def test_agent_version_detail_validates_orm_model_config_and_dumps_external_key() -> None:
    class AgentVersionRecord:
        id = uuid4()
        agent_id = uuid4()
        provider_id = uuid4()
        version_number = 3
        system_prompt = "You are careful."
        model_config = {"temperature": 0}
        tool_allowlist = ["search_sop"]
        mcp_server_ids = ["change-docs"]
        published_by = "ops@example.com"
        published_at = datetime(2026, 5, 26, tzinfo=UTC)

    detail = AgentVersionDetail.model_validate(AgentVersionRecord())
    payload = detail.model_dump(mode="json")

    assert detail.model_parameters == {"temperature": 0}
    assert payload["provider_id"] == str(AgentVersionRecord.provider_id)
    assert "model" not in payload
    assert payload["model_config"] == {"temperature": 0}
    assert "model_parameters" not in payload


def test_agent_test_run_rejects_empty_messages() -> None:
    with pytest.raises(ValidationError):
        AgentTestRunCreate(messages=[])


def test_agent_test_run_rejects_version_id_and_version_number_together() -> None:
    with pytest.raises(ValidationError):
        AgentTestRunCreate(
            version_id=uuid4(),
            version_number=1,
            messages=[{"role": "user", "content": "Review this change."}],
        )

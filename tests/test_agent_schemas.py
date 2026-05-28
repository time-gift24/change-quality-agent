from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.agents import (
    AgentCreate,
    AgentDraftConfig,
    AgentVersionDetail,
)


def test_agent_create_accepts_initial_draft() -> None:
    request = AgentCreate(
        display_name="Release Reviewer",
        description="Checks release quality",
        draft=AgentDraftConfig(
            system_prompt="You are careful.",
            model="openai:gpt-5-mini",
            model_config={"temperature": 0},
            tool_allowlist=["search_sop"],
            mcp_server_ids=["change-docs"],
        ),
    )

    assert request.display_name == "Release Reviewer"
    assert request.draft.model == "openai:gpt-5-mini"


def test_agent_draft_config_dumps_external_model_config_key() -> None:
    draft = AgentDraftConfig(
        system_prompt="You are careful.",
        model="openai:gpt-5-mini",
        model_config={"temperature": 0},
    )

    payload = draft.model_dump(mode="json")

    assert payload["model_config"] == {"temperature": 0}
    assert "model_parameters" not in payload


def test_agent_draft_config_accepts_provider_id_with_bare_model() -> None:
    provider_id = uuid4()
    draft = AgentDraftConfig(
        system_prompt="You are careful.",
        model="gpt-5-mini",
        provider_id=provider_id,
        model_config={"temperature": 0},
    )

    payload = draft.model_dump(mode="json")

    assert draft.provider_id == provider_id
    assert payload["provider_id"] == str(provider_id)


def test_agent_draft_config_rejects_provider_id_with_prefixed_model() -> None:
    with pytest.raises(ValidationError, match="provider_id requires bare model name"):
        AgentDraftConfig(
            system_prompt="You are careful.",
            model="openai:gpt-5-mini",
            provider_id=uuid4(),
        )


def test_agent_draft_config_allows_codeagent_without_provider_id() -> None:
    draft = AgentDraftConfig(
        system_prompt="You are careful.",
        model="codeagent:deepseek-v4-pro",
    )

    assert draft.model == "codeagent:deepseek-v4-pro"
    assert draft.provider_id is None


def test_agent_version_detail_validates_orm_model_config_and_dumps_external_key() -> None:
    class AgentVersionRecord:
        id = uuid4()
        agent_id = uuid4()
        version_number = 3
        system_prompt = "You are careful."
        model = "openai:gpt-5-mini"
        provider_id = uuid4()
        model_config = {"temperature": 0}
        tool_allowlist = ["search_sop"]
        mcp_server_ids = ["change-docs"]
        published_by = "ops@example.com"
        published_at = datetime(2026, 5, 26, tzinfo=UTC)

    detail = AgentVersionDetail.model_validate(AgentVersionRecord())
    payload = detail.model_dump(mode="json")

    assert detail.model_parameters == {"temperature": 0}
    assert detail.provider_id == AgentVersionRecord.provider_id
    assert payload["model_config"] == {"temperature": 0}
    assert "model_parameters" not in payload

from app.schemas.agents import AgentCreate, AgentDraftConfig, AgentTestRunCreate


def test_agent_create_accepts_initial_draft() -> None:
    request = AgentCreate(
        key="release-reviewer",
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

    assert request.key == "release-reviewer"
    assert request.draft.model == "openai:gpt-5-mini"


def test_agent_test_run_requires_messages() -> None:
    request = AgentTestRunCreate(
        messages=[{"role": "user", "content": "Review this change."}]
    )

    assert request.messages[0].role == "user"
    assert request.version_number is None

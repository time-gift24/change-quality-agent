from app.agent.sop_quality.display import (
    display_state_from_graph_values,
    display_state_from_session_messages,
)


def test_running_display_does_not_claim_no_issues_before_findings_exist() -> None:
    state = display_state_from_graph_values(
        {"sop_snapshot": {"sop_id": "release-checklist"}},
        latest_sequence=1,
        is_running=True,
    )

    summarize_result = state["nodes"].get("summarize_result")

    assert (
        summarize_result is None or "No obvious" not in summarize_result["streamText"]
    )


def test_completed_empty_findings_can_report_no_structural_issues() -> None:
    state = display_state_from_graph_values(
        {
            "sop_snapshot": {"sop_id": "release-checklist"},
            "findings": [],
        },
        latest_sequence=2,
        is_running=False,
    )

    assert state["nodes"]["summarize_result"]["streamText"] == (
        "No obvious structural issues found."
    )


def test_display_from_session_messages_groups_by_step() -> None:
    messages = [
        {"step": "load_sop", "role": "assistant", "content": "Loaded SOP release."},
        {"step": "review_sop", "role": "assistant", "content": "Review in progress"},
        {"step": "review_sop", "role": "assistant", "content": "Review complete."},
        {"step": "summarize_result", "role": "assistant", "content": "## Report"},
        {"step": "submit_result", "role": "assistant", "content": "Submitted."},
    ]
    state = display_state_from_session_messages(
        messages,
        latest_sequence=5,
        is_running=False,
    )

    assert state["nodes"]["load_sop"]["status"] == "done"
    assert state["nodes"]["load_sop"]["streamText"] == "Loaded SOP release."
    # review_sop concatenates messages
    assert "Review complete." in state["nodes"]["review_sop"]["streamText"]
    assert state["nodes"]["summarize_result"]["status"] == "done"
    assert state["nodes"]["submit_result"]["status"] == "done"


def test_display_from_session_messages_running_status() -> None:
    messages = [
        {"step": "load_sop", "role": "assistant", "content": "Loaded."},
        {"step": "review_sop", "role": "assistant", "content": "Thinking..."},
    ]
    state = display_state_from_session_messages(
        messages,
        latest_sequence=2,
        is_running=True,
    )

    assert state["nodes"]["load_sop"]["status"] == "done"
    assert state["nodes"]["review_sop"]["status"] == "running"


def test_display_from_empty_session_messages() -> None:
    state = display_state_from_session_messages(
        [],
        latest_sequence=0,
        is_running=True,
    )

    assert state["nodes"] == {}
    assert state["is_running"] is True

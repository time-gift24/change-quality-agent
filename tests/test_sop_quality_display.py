from app.agent.sop_quality.display import display_state_from_graph_values


def test_running_display_does_not_claim_no_issues_before_findings_exist() -> None:
    state = display_state_from_graph_values(
        {"sop_snapshot": {"sop_id": "release-checklist"}},
        latest_sequence=1,
        is_running=True,
    )

    summarize_result = state["nodes"].get("summarize_result")

    assert summarize_result is None or "No obvious" not in summarize_result["streamText"]


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

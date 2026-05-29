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

    assert summarize_result is None or "未发现明显" not in summarize_result["streamText"]


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
        "未发现明显结构性问题。"
    )


def test_display_from_session_messages_groups_by_step() -> None:
    messages = [
        {"step": "load_sop", "role": "assistant", "content": "已读取 SOP release。"},
        {"step": "review_sop", "role": "assistant", "content": "正在评审"},
        {"step": "review_sop", "role": "assistant", "content": "评审完成。"},
        {"step": "summarize_result", "role": "assistant", "content": "## 报告"},
        {"step": "submit_result", "role": "assistant", "content": "已提交。"},
    ]
    state = display_state_from_session_messages(
        messages,
        latest_sequence=5,
        is_running=False,
    )

    assert state["nodes"]["load_sop"]["status"] == "done"
    assert state["nodes"]["load_sop"]["streamText"] == "已读取 SOP release。"
    # review_sop concatenates messages
    assert "评审完成。" in state["nodes"]["review_sop"]["streamText"]
    assert state["nodes"]["summarize_result"]["status"] == "done"
    assert state["nodes"]["submit_result"]["status"] == "done"


def test_display_from_session_messages_running_status() -> None:
    messages = [
        {"step": "load_sop", "role": "assistant", "content": "已读取。"},
        {"step": "review_sop", "role": "assistant", "content": "正在思考..."},
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

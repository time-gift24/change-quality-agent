from typing import Any


def display_state_from_graph_values(
    values: dict[str, Any],
    *,
    latest_sequence: int = 0,
    is_running: bool = False,
) -> dict[str, Any]:
    raw_findings = values.get("findings")
    findings = raw_findings if isinstance(raw_findings, list) else None
    result = values.get("result") if isinstance(values.get("result"), dict) else None
    submission_result = (
        values.get("submission_result")
        if isinstance(values.get("submission_result"), dict)
        else None
    )
    nodes: dict[str, Any] = {}
    if values.get("sop_snapshot"):
        nodes["load_sop"] = {"status": "done", "streamText": "SOP snapshot loaded."}
    if isinstance(values.get("review_output"), str):
        nodes["review_sop"] = {
            "status": "done" if not is_running else "running",
            "streamText": values["review_output"],
        }
    if findings is not None:
        nodes["summarize_result"] = {
            "status": "done" if not is_running else "running",
            "streamText": _findings_text(findings),
        }
    if result:
        nodes["summarize_result"] = {
            "status": "done",
            "streamText": result.get("report_markdown") or result.get("summary") or "",
        }
    if submission_result:
        nodes["submit_result"] = {
            "status": "done",
            "streamText": _submission_text(submission_result),
        }
    return {
        "latest_sequence": latest_sequence,
        "nodes": nodes,
        "is_running": is_running,
    }


def _findings_text(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "No obvious structural issues found."
    return "\n".join(f"- {item.get('title', 'Finding')}" for item in findings)


def _submission_text(submission_result: dict[str, Any]) -> str:
    status = submission_result.get("external_status") or submission_result.get("status")
    return f"External submission: {status or 'completed'}."

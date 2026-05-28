from typing import Any


def display_state_from_graph_values(
    values: dict[str, Any],
    *,
    latest_sequence: int = 0,
    is_running: bool = False,
) -> dict[str, Any]:
    findings = values.get("findings") if isinstance(values.get("findings"), list) else []
    result = values.get("result") if isinstance(values.get("result"), dict) else None
    nodes: dict[str, Any] = {}
    if values.get("sop_snapshot"):
        nodes["load_sop"] = {"status": "done", "streamText": "SOP snapshot loaded."}
    if findings is not None:
        nodes["check_steps"] = {
            "status": "done" if not is_running else "running",
            "streamText": _findings_text(findings),
        }
    if result:
        nodes["summarize_result"] = {
            "status": "done",
            "streamText": result.get("report_markdown") or result.get("summary") or "",
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

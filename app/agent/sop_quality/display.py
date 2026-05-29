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


def display_state_from_session_messages(
    messages: list[dict[str, Any]],
    *,
    latest_sequence: int = 0,
    is_running: bool = False,
) -> dict[str, Any]:
    """Project session messages into the SOP display state grouped by step.

    Each session message is expected to carry a `step` key (either at the top
    level or under `additional_kwargs.step`). The last user-visible step is
    treated as the in-progress one when `is_running` is True; earlier steps
    are considered done.
    """
    ordered_steps = ("load_sop", "review_sop", "summarize_result", "submit_result")
    grouped: dict[str, list[str]] = {step: [] for step in ordered_steps}
    seen_order: list[str] = []

    for message in messages:
        step = _message_step(message)
        if step is None or step not in grouped:
            continue
        content = message.get("content") or ""
        if not isinstance(content, str):
            continue
        grouped[step].append(content)
        if step not in seen_order:
            seen_order.append(step)

    nodes: dict[str, Any] = {}
    last_seen = seen_order[-1] if seen_order else None
    for step in seen_order:
        chunks = grouped[step]
        if not chunks:
            continue
        status = "running" if (is_running and step == last_seen) else "done"
        nodes[step] = {
            "status": status,
            "streamText": "\n".join(chunks),
        }
    return {
        "latest_sequence": latest_sequence,
        "nodes": nodes,
        "is_running": is_running,
    }


def _message_step(message: dict[str, Any]) -> str | None:
    step = message.get("step")
    if isinstance(step, str):
        return step
    kwargs = message.get("additional_kwargs")
    if isinstance(kwargs, dict):
        step = kwargs.get("step")
        if isinstance(step, str):
            return step
    return None


def _findings_text(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "No obvious structural issues found."
    return "\n".join(f"- {item.get('title', 'Finding')}" for item in findings)


def _submission_text(submission_result: dict[str, Any]) -> str:
    status = submission_result.get("external_status") or submission_result.get("status")
    return f"External submission: {status or 'completed'}."

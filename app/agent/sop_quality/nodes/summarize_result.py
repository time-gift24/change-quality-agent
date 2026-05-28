from app.agent.sop_quality.state import SopQualityState


async def summarize_result(state: SopQualityState) -> SopQualityState:
    existing_result = state.get("result")
    if isinstance(existing_result, dict):
        return {
            "summary": existing_result.get("summary", ""),
            "report_markdown": existing_result.get("report_markdown", ""),
            "quality_result": existing_result.get("quality_result", "pass"),
            "findings": existing_result.get("findings", []),
            "result": existing_result,
        }

    findings = state.get("findings", [])
    quality_result = state.get("quality_result", "pass")
    summary = (
        "No blocking SOP quality issues found."
        if not findings
        else f"Found {len(findings)} SOP quality issue(s)."
    )
    report_markdown = _report_markdown(summary, findings)
    return {
        "summary": summary,
        "report_markdown": report_markdown,
        "result": {
            "quality_result": quality_result,
            "summary": summary,
            "findings": findings,
            "report_markdown": report_markdown,
        },
    }


def _report_markdown(summary: str, findings: list[dict]) -> str:
    if not findings:
        return f"## SOP Quality Report\n\n{summary}\n"
    lines = ["## SOP Quality Report", "", summary, ""]
    for finding in findings:
        lines.append(
            f"- **{finding['severity']}** {finding['title']}: "
            f"{finding['recommendation']}"
        )
    return "\n".join(lines)

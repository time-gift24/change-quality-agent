from app.agent.sop_quality.nodes.review_sop import (
    _load_json_object,
    _normalize_result,
)
from app.agent.sop_quality.state import (
    SopQualityFinding,
    SopQualityReviewResult,
    SopQualityState,
)
from app.core.agent_streaming import SessionMessageWriter


def make_summarize_result(message_writer: SessionMessageWriter):
    async def summarize_result(state: SopQualityState) -> SopQualityState:
        result_state = _summarize_result_state(state)
        result = result_state.get("result")
        if isinstance(result, dict):
            content = result.get("report_markdown") or result.get("summary") or ""
            await message_writer.append_step_message(
                step="summarize_result",
                role="assistant",
                content=content,
                additional_kwargs={
                    "kind": "step_message",
                    "step": "summarize_result",
                    "channel": "summary",
                },
            )
        return result_state

    return summarize_result


def _summarize_result_state(state: SopQualityState) -> SopQualityState:
    existing_result = state.get("result")
    if isinstance(existing_result, dict):
        return {
            "summary": existing_result.get("summary", ""),
            "report_markdown": existing_result.get("report_markdown", ""),
            "quality_result": existing_result.get("quality_result", "pass"),
            "findings": existing_result.get("findings", []),
            "result": existing_result,
        }

    review_output = state.get("review_output")
    if isinstance(review_output, str) and review_output.strip():
        result = {
            **_result_from_review_output(review_output),
            "review_output": review_output.strip(),
        }
        return {
            "summary": result["summary"],
            "report_markdown": result["report_markdown"],
            "quality_result": result["quality_result"],
            "findings": result["findings"],
            "result": result,
        }

    findings = state.get("findings", [])
    quality_result = state.get("quality_result", "pass")
    summary = (
        "未发现阻塞性的 SOP 质量问题。"
        if not findings
        else f"发现 {len(findings)} 个 SOP 质量问题。"
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


def _result_from_review_output(review_output: str) -> SopQualityReviewResult:
    try:
        return _normalize_result(_load_json_object(review_output))
    except ValueError:
        summary = _first_non_empty_line(review_output)
        return {
            "quality_result": "warn",
            "summary": summary,
            "findings": [],
            "report_markdown": review_output.strip(),
        }


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "SOP 质量评审已完成。"


def _report_markdown(summary: str, findings: list[SopQualityFinding]) -> str:
    if not findings:
        return f"## SOP 质量报告\n\n{summary}\n"
    lines = ["## SOP 质量报告", "", summary, ""]
    for finding in findings:
        lines.append(
            f"- **{finding['severity']}** {finding['title']}: "
            f"{finding['recommendation']}"
        )
    return "\n".join(lines)

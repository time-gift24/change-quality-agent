import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.sop_quality.state import SopQualityState
from app.core.agent_streaming import DeepAgentRunInput, DeepAgentStreamRunner

CreateDeepagents = Callable[..., Awaitable[Any]]

SYSTEM_PROMPT = """You are a strict SOP quality reviewer.
Review the SOP for operational quality, completeness, ambiguity, and execution risk.
Use any available tools that help the review. Do not hide important caveats."""

SEVERITY_ALIASES = {
    "info": "low",
    "informational": "low",
    "minor": "low",
    "low": "low",
    "低": "low",
    "低风险": "low",
    "medium": "medium",
    "moderate": "medium",
    "warning": "medium",
    "warn": "medium",
    "中": "medium",
    "中等": "medium",
    "中风险": "medium",
    "high": "high",
    "critical": "high",
    "severe": "high",
    "blocker": "high",
    "blocking": "high",
    "高": "high",
    "高风险": "high",
    "严重": "high",
}


def make_review_sop(
    create_deepagents: CreateDeepagents,
    deepagent_stream_runner: DeepAgentStreamRunner,
) -> Callable[[SopQualityState], Awaitable[SopQualityState]]:
    async def review_sop(state: SopQualityState) -> SopQualityState:
        agent = await create_deepagents(
            system_prompt=SYSTEM_PROMPT,
            model_config={"temperature": 0},
        )
        result = await deepagent_stream_runner.run_step(
            agent=agent,
            step="review_sop",
            input=DeepAgentRunInput(messages=[_user_message(state)]),
        )
        return {"review_output": result.final_text}

    return review_sop


def _user_message(state: SopQualityState) -> dict[str, str]:
    payload = {
        "check_id": state.get("check_id"),
        "sop_id": state.get("sop_id"),
        "env_key": state.get("env_key"),
        "sop_snapshot": state.get("sop_snapshot") or {},
    }
    return {
        "role": "user",
        "content": (
            "Review this SOP for operational quality, completeness, ambiguity, "
            "and execution risk. Use the format that best communicates your review.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}"
        ),
    }


def _load_json_object(text: str) -> dict[str, Any]:
    candidate = _strip_code_fence(text.strip())
    start = candidate.find("{")
    if start < 0:
        raise ValueError("SOP quality agent did not return valid JSON.")
    try:
        parsed, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except json.JSONDecodeError as exc:
        raise ValueError("SOP quality agent did not return valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("SOP quality agent did not return a JSON object.")
    return parsed


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _normalize_result(parsed: dict[str, Any]) -> dict[str, Any]:
    quality_result = parsed.get("quality_result")
    if quality_result not in {"pass", "warn", "fail"}:
        raise ValueError("SOP quality agent returned an invalid quality_result.")

    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("SOP quality agent returned an invalid summary.")

    findings = parsed.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("SOP quality agent returned invalid findings.")
    normalized_findings = [_normalize_finding(finding) for finding in findings]

    report_markdown = parsed.get("report_markdown")
    if not isinstance(report_markdown, str) or not report_markdown.strip():
        report_markdown = _fallback_report(summary, normalized_findings)

    return {
        "quality_result": quality_result,
        "summary": summary.strip(),
        "findings": normalized_findings,
        "report_markdown": report_markdown,
    }


def _normalize_finding(finding: Any) -> dict[str, str]:
    if not isinstance(finding, dict):
        raise ValueError("SOP quality agent returned invalid findings.")
    severity = _normalize_severity(finding.get("severity"))
    title = finding.get("title")
    recommendation = finding.get("recommendation")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("SOP quality agent returned an invalid finding title.")
    if not isinstance(recommendation, str) or not recommendation.strip():
        raise ValueError("SOP quality agent returned an invalid recommendation.")
    return {
        "severity": severity,
        "title": title.strip(),
        "recommendation": recommendation.strip(),
    }


def _normalize_severity(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("SOP quality agent returned an invalid finding severity.")
    severity = SEVERITY_ALIASES.get(value.strip().lower())
    if severity is None:
        raise ValueError("SOP quality agent returned an invalid finding severity.")
    return severity


def _fallback_report(summary: str, findings: list[dict[str, str]]) -> str:
    if not findings:
        return f"## SOP Quality Report\n\n{summary}\n"
    lines = ["## SOP Quality Report", "", summary, ""]
    for finding in findings:
        lines.append(
            f"- **{finding['severity']}** {finding['title']}: "
            f"{finding['recommendation']}"
        )
    return "\n".join(lines)

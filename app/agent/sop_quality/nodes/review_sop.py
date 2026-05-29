import json
from collections.abc import Awaitable, Callable
from typing import cast

from app.agent.sop_quality.state import (
    SopQualityFinding,
    SopQualityFindingSeverity,
    SopQualityReviewResult,
    SopQualityResultValue,
    SopQualityState,
)
from app.core.agent_streaming import DeepAgentRunInput, DeepAgentStreamRunner
from app.core.json_types import JsonObject
from app.core.llm_model_config import LlmModelParameters

CreateDeepagents = Callable[..., Awaitable[object]]

SYSTEM_PROMPT = """你是严格的 SOP 质量评审专家。
请从可执行性、完整性、歧义、风险控制、职责边界和回滚准备等方面审查 SOP。
可以使用任何有助于评审的工具，不要隐藏关键风险或前提条件。

输出优先使用 JSON 对象，字段保持英文以兼容系统：
- quality_result: pass | warn | fail
  - pass：未发现需要整改的问题。
  - warn：存在非阻塞问题，SOP 可以继续推进但应补充或澄清。
  - fail：存在阻塞问题，SOP 在整改前不应执行。
- summary: 中文摘要。
- findings: 中文问题列表，每项包含 severity、title、recommendation。
- findings[].severity 只能使用：低风险、中风险、高风险。
- report_markdown: 中文 Markdown 报告正文。"""

SEVERITY_ALIASES = {
    "info": "低风险",
    "informational": "低风险",
    "minor": "低风险",
    "low": "低风险",
    "低": "低风险",
    "低风险": "低风险",
    "medium": "中风险",
    "moderate": "中风险",
    "warning": "中风险",
    "warn": "中风险",
    "中": "中风险",
    "中等": "中风险",
    "中风险": "中风险",
    "high": "高风险",
    "critical": "高风险",
    "severe": "高风险",
    "blocker": "高风险",
    "blocking": "高风险",
    "高": "高风险",
    "高风险": "高风险",
    "严重": "高风险",
}


def make_review_sop(
    create_deepagents: CreateDeepagents,
    deepagent_stream_runner: DeepAgentStreamRunner,
) -> Callable[[SopQualityState], Awaitable[SopQualityState]]:
    async def review_sop(state: SopQualityState) -> SopQualityState:
        agent = await create_deepagents(
            system_prompt=SYSTEM_PROMPT,
            model_config=LlmModelParameters(temperature=0),
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
            "请评审这份 SOP 的可执行性、完整性、歧义、风险控制、职责边界和回滚准备。"
            "请用中文输出，优先返回符合系统提示词约定的 JSON 对象。\n\n"
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}"
        ),
    }


def _load_json_object(text: str) -> JsonObject:
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
    return cast(JsonObject, parsed)


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _normalize_result(parsed: JsonObject) -> SopQualityReviewResult:
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
        "quality_result": cast(SopQualityResultValue, quality_result),
        "summary": summary.strip(),
        "findings": normalized_findings,
        "report_markdown": report_markdown,
    }


def _normalize_finding(finding: object) -> SopQualityFinding:
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


def _normalize_severity(value: object) -> SopQualityFindingSeverity:
    if not isinstance(value, str):
        raise ValueError("SOP quality agent returned an invalid finding severity.")
    severity = SEVERITY_ALIASES.get(value.strip().lower())
    if severity is None:
        raise ValueError("SOP quality agent returned an invalid finding severity.")
    return cast(SopQualityFindingSeverity, severity)


def _fallback_report(summary: str, findings: list[SopQualityFinding]) -> str:
    if not findings:
        return f"## SOP 质量报告\n\n{summary}\n"
    lines = ["## SOP 质量报告", "", summary, ""]
    for finding in findings:
        lines.append(
            f"- **{finding['severity']}** {finding['title']}: "
            f"{finding['recommendation']}"
        )
    return "\n".join(lines)

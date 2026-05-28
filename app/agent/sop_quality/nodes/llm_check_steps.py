import json
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.sop_quality.state import SopQualityState
from app.core.create_deepagents_by_llm_provider import create_deepagents_by_llm_provider
from app.core.stream_events import runtime_stream_event

AgentFactory = Callable[..., Awaitable[Any]]
LiveEventCallback = Callable[[dict[str, Any]], Any]

SYSTEM_PROMPT = """You are a strict SOP quality reviewer.
Return only one JSON object with these fields:
- quality_result: one of "pass", "warn", or "fail"
- summary: concise user-facing summary
- findings: list of objects with severity, title, and recommendation
- finding severity must be one of "low", "medium", or "high"
- report_markdown: markdown report for display
Do not include prose outside the JSON object."""

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


def make_llm_check_steps(
    llm_provider_repository: Any,
    *,
    create_deep_agent_by_provider: AgentFactory = create_deepagents_by_llm_provider,
    on_live_event: LiveEventCallback | None = None,
) -> Callable[[SopQualityState], Awaitable[SopQualityState]]:
    agent: Any | None = None

    async def llm_check_steps(state: SopQualityState) -> SopQualityState:
        nonlocal agent
        if agent is None:
            agent = await create_deep_agent_by_provider(
                llm_provider_repository,
                system_prompt=SYSTEM_PROMPT,
                model_config={"temperature": 0},
            )

        output = await _run_agent(
            agent,
            {"messages": [_user_message(state)]},
            on_live_event=on_live_event,
        )
        result = _parse_agent_result(output)
        await _publish_live_event(
            on_live_event,
            {
                "type": "messages",
                "node": "check_steps",
                "channel": "summary",
                "message": result["report_markdown"] or result["summary"],
            },
        )
        return {
            "quality_result": result["quality_result"],
            "summary": result["summary"],
            "findings": result["findings"],
            "report_markdown": result["report_markdown"],
            "result": result,
        }

    return llm_check_steps


async def _run_agent(
    agent: Any,
    payload: dict[str, Any],
    *,
    on_live_event: LiveEventCallback | None,
) -> Any:
    astream = getattr(agent, "astream", None)
    if astream is None:
        return await _invoke_agent(agent, payload)

    chunks: list[str] = []
    thinking_published = False
    stream = astream(payload, stream_mode=["messages", "updates"])
    if inspect.isawaitable(stream):
        stream = await stream

    async for chunk_type, chunk in stream:
        event = runtime_stream_event(chunk_type, chunk)
        event["node"] = event.get("node") or "check_steps"
        if _reasoning_delta(chunk) and not thinking_published:
            thinking_published = True
            await _publish_live_event(
                on_live_event,
                {
                    "type": "messages",
                    "node": event["node"],
                    "channel": "thinking",
                    "message": "正在分析 SOP...",
                },
            )
        delta = _event_delta(event)
        if delta:
            chunks.append(delta)
            await _publish_live_event(
                on_live_event,
                {
                    "type": "messages",
                    "node": event["node"],
                    "message": delta,
                },
            )
        elif event["type"] == "updates":
            await _publish_live_event(
                on_live_event,
                {
                    "type": "updates",
                    "node": event["node"],
                },
            )

    if chunks:
        return {"messages": [{"role": "assistant", "content": "".join(chunks)}]}
    return await _invoke_agent(agent, payload)


async def _invoke_agent(agent: Any, payload: dict[str, Any]) -> Any:
    invoke = getattr(agent, "ainvoke", None)
    if invoke is not None:
        output = invoke(payload)
        if inspect.isawaitable(output):
            return await output
        return output

    invoke = getattr(agent, "invoke", None)
    if invoke is None:
        raise TypeError("SOP quality agent does not support invoke or ainvoke.")

    output = invoke(payload)
    if inspect.isawaitable(output):
        return await output
    return output


async def _publish_live_event(
    on_live_event: LiveEventCallback | None,
    event: dict[str, Any],
) -> None:
    if on_live_event is None:
        return
    result = on_live_event(event)
    if inspect.isawaitable(result):
        await result


def _event_delta(event: dict[str, Any]) -> str | None:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    delta = payload.get("delta")
    return delta if isinstance(delta, str) and delta else None


def _reasoning_delta(chunk: Any) -> str | None:
    message = chunk[0] if _is_message_tuple(chunk) else chunk
    additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        for key in ("reasoning_content", "reasoning"):
            value = additional_kwargs.get(key)
            if isinstance(value, str) and value:
                return value
    if isinstance(message, dict):
        for key in ("reasoning_content", "reasoning"):
            value = message.get(key)
            if isinstance(value, str) and value:
                return value
        nested = message.get("additional_kwargs")
        if isinstance(nested, dict):
            for key in ("reasoning_content", "reasoning"):
                value = nested.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def _is_message_tuple(chunk: Any) -> bool:
    return isinstance(chunk, tuple | list) and len(chunk) >= 2


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
            "and execution risk. Return the required JSON object.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}"
        ),
    }


def _parse_agent_result(output: Any) -> dict[str, Any]:
    if isinstance(output, dict) and isinstance(output.get("structured_response"), dict):
        parsed = output["structured_response"]
    else:
        parsed = _load_json_object(_agent_text(output))
    return _normalize_result(parsed)


def _agent_text(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        messages = output.get("messages")
        if isinstance(messages, list) and messages:
            return _message_content(messages[-1])
        content = output.get("content")
        if content is not None:
            return _content_text(content)
    content = getattr(output, "content", None)
    if content is not None:
        return _content_text(content)
    raise ValueError("SOP quality agent did not return valid JSON.")


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return _content_text(message.get("content"))
    return _content_text(getattr(message, "content", None))


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    raise ValueError("SOP quality agent did not return valid JSON.")


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

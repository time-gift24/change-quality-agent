from typing import Any

from app.agent.sop_quality.state import SopQualityState


async def check_steps(state: SopQualityState) -> SopQualityState:
    payload = _payload(state)
    findings: list[dict[str, Any]] = []

    if not payload.get("title"):
        findings.append(
            {
                "severity": "medium",
                "title": "Missing SOP title",
                "recommendation": "Add a clear SOP title.",
            }
        )

    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        findings.append(
            {
                "severity": "high",
                "title": "Missing SOP steps",
                "recommendation": "Add executable SOP steps before quality approval.",
            }
        )

    quality_result = "pass" if not findings else "warn"
    return {"findings": findings, "quality_result": quality_result}


def _payload(state: SopQualityState) -> dict[str, Any]:
    snapshot = state.get("sop_snapshot") or {}
    payload = snapshot.get("payload")
    return payload if isinstance(payload, dict) else {}

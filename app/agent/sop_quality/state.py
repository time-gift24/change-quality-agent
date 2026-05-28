from typing import Any, TypedDict


class SopQualityState(TypedDict, total=False):
    check_id: str
    sop_id: str
    env_key: str
    sop_snapshot: dict[str, Any]
    messages: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    summary: str
    quality_result: str
    report_markdown: str
    result: dict[str, Any]

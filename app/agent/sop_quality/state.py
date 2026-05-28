from typing import Any, TypedDict


class SopQualityState(TypedDict, total=False):
    check_id: str
    sop_id: str
    env_key: str
    sop_snapshot: dict[str, Any]
    messages: list[dict[str, Any]]
    review_output: str
    findings: list[dict[str, Any]]
    summary: str
    quality_result: str
    report_markdown: str
    submission_result: dict[str, Any]
    result: dict[str, Any]

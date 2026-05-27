from typing import Any, TypedDict


class SopQualityState(TypedDict, total=False):
    run_id: str
    sop_snapshot: dict[str, Any]
    messages: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    status: str

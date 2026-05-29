from typing import TypedDict

from app.core.json_types import JsonObject


class SopQualityState(TypedDict, total=False):
    check_id: str
    sop_id: str
    env_key: str
    sop_snapshot: JsonObject
    messages: list[JsonObject]
    review_output: str
    findings: list[JsonObject]
    summary: str
    quality_result: str
    report_markdown: str
    submission_result: JsonObject
    result: JsonObject

from typing import Literal, TypedDict

from app.core.json_types import JsonObject

SopQualityResultValue = Literal["pass", "warn", "fail"]
SopQualityFindingSeverity = Literal["low", "medium", "high"]


class SopQualityFinding(TypedDict):
    severity: SopQualityFindingSeverity
    title: str
    recommendation: str


class SopQualityReviewResult(TypedDict, total=False):
    quality_result: SopQualityResultValue
    summary: str
    findings: list[SopQualityFinding]
    report_markdown: str
    review_output: str
    submission_result: JsonObject


class SopQualityError(TypedDict):
    type: str
    message: str


class SopQualityState(TypedDict, total=False):
    check_id: str
    sop_id: str
    env_key: str
    sop_snapshot: JsonObject
    messages: list[JsonObject]
    review_output: str
    findings: list[SopQualityFinding]
    summary: str
    quality_result: SopQualityResultValue
    report_markdown: str
    submission_result: JsonObject
    result: SopQualityReviewResult

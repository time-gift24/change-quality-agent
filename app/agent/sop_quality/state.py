from typing import Literal, TypedDict

from app.core.json_types import JsonObject

SopQualityResultValue = Literal["pass", "warn", "fail"]
SopQualityFindingSeverity = Literal["low", "medium", "high"]


class SopQualityFinding(TypedDict):
    """One actionable issue identified while reviewing an SOP."""

    # Normalized risk level for sorting, filtering, and UI badges.
    severity: SopQualityFindingSeverity
    # Short, user-facing issue name.
    title: str
    # Concrete remediation guidance for the SOP owner.
    recommendation: str


class SopQualityReviewResult(TypedDict, total=False):
    """Canonical SOP quality review artifact persisted after graph execution."""

    # Overall review verdict. `warn` means usable with non-blocking issues.
    quality_result: SopQualityResultValue
    # Concise human-readable review summary.
    summary: str
    # Structured review issues. Empty means no specific SOP defects were found.
    findings: list[SopQualityFinding]
    # Final user-facing report body shown in messages and detail views.
    report_markdown: str
    # Raw DeepAgent/LLM review text kept for traceability and debugging.
    review_output: str
    # JSON-safe receipt returned by the external result submission boundary.
    submission_result: JsonObject


class SopQualityError(TypedDict):
    type: str
    message: str


class SopQualityState(TypedDict, total=False):
    """LangGraph state shared by SOP quality nodes during one check run."""

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

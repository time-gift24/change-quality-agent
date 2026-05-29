from typing import Literal, TypedDict

from app.core.json_types import JsonObject

SopQualityResultValue = Literal["pass", "warn", "fail"]
SopQualityFindingSeverity = Literal["低风险", "中风险", "高风险"]


class SopQualityFinding(TypedDict):
    """SOP 评审中识别出的一个可执行问题。"""

    # 归一化风险等级，用于排序、筛选和 UI 标签。
    severity: SopQualityFindingSeverity
    # 面向用户的简短问题标题。
    title: str
    # 给 SOP 负责人的具体整改建议。
    recommendation: str


class SopQualityReviewResult(TypedDict, total=False):
    """SOP 质量检查图执行完成后持久化的标准评审产物。"""

    # 总体评审结论。`warn` 表示可用但存在非阻塞问题。
    quality_result: SopQualityResultValue
    # 面向人的简短评审摘要。
    summary: str
    # 结构化评审问题列表。空列表表示未发现明确的 SOP 缺陷。
    findings: list[SopQualityFinding]
    # 最终面向用户展示的 Markdown 报告正文。
    report_markdown: str
    # DeepAgent/LLM 原始评审文本，用于追踪和排查。
    review_output: str
    # 外部结果提交边界返回的 JSON-safe 回执。
    submission_result: JsonObject


class SopQualityError(TypedDict):
    type: str
    message: str


class SopQualityState(TypedDict, total=False):
    """一次 SOP 质量检查运行中各 LangGraph 节点共享的状态。"""

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

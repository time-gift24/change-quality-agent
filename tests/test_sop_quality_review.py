from app.agent.sop_quality.nodes.review_sop import (
    SYSTEM_PROMPT,
    _normalize_result,
    _user_message,
)


def test_review_prompt_uses_chinese_instructions_and_risk_levels() -> None:
    assert "你是严格的 SOP 质量评审专家" in SYSTEM_PROMPT
    assert "低风险" in SYSTEM_PROMPT
    assert "中风险" in SYSTEM_PROMPT
    assert "高风险" in SYSTEM_PROMPT

    message = _user_message(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {"title": "上线检查清单"},
        }
    )

    assert message["role"] == "user"
    assert "请评审这份 SOP" in message["content"]
    assert "上线检查清单" in message["content"]


def test_review_result_normalizes_finding_severity_to_chinese_risk_levels() -> None:
    result = _normalize_result(
        {
            "quality_result": "warn",
            "summary": "需要补充回滚说明。",
            "findings": [
                {
                    "severity": "medium",
                    "title": "缺少回滚步骤",
                    "recommendation": "补充失败后的回滚负责人和执行步骤。",
                },
                {
                    "severity": "高风险",
                    "title": "缺少审批门禁",
                    "recommendation": "发布前增加明确审批节点。",
                },
            ],
        }
    )

    assert result["findings"] == [
        {
            "severity": "中风险",
            "title": "缺少回滚步骤",
            "recommendation": "补充失败后的回滚负责人和执行步骤。",
        },
        {
            "severity": "高风险",
            "title": "缺少审批门禁",
            "recommendation": "发布前增加明确审批节点。",
        },
    ]
    assert result["report_markdown"].startswith("## SOP 质量报告")

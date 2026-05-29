import json
from typing import Protocol


class SopQualityRunLike(Protocol):
    subject_snapshot: object
    subject_id: object


def build_sop_quality_user_message(run: SopQualityRunLike) -> dict[str, str]:
    sop_snapshot = json.dumps(
        run.subject_snapshot,
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "role": "user",
        "content": (
            "请对以下 SOP 快照执行质量检查，指出步骤完整性、发布风险和需要补充的验证项。\n\n"
            f"SOP ID: {run.subject_id}\n"
            f"SOP Snapshot JSON:\n{sop_snapshot}"
        ),
    }

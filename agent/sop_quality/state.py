from typing import Any, TypedDict


class SopQualityState(TypedDict, total=False):
    run_id: str
    sop_snapshot: dict[str, Any]
    status: str


from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SopQualityCheckStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    interrupted = "interrupted"


class SopQualityCheckStartResponse(BaseModel):
    check_id: UUID
    status: SopQualityCheckStatus
    created: bool
    status_url: str
    stream_url: str


class SopQualityCheckSummary(BaseModel):
    check_id: UUID
    sop_id: str
    env_key: str
    status: SopQualityCheckStatus
    quality_result: str | None = None
    latest_sequence: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_summary: str | None = None


class SopQualityDisplayState(BaseModel):
    model_config = ConfigDict(extra="allow")

    latest_sequence: int = 0
    nodes: dict[str, Any] = Field(default_factory=dict)
    is_running: bool = False


class SopQualityCheckDetail(SopQualityCheckSummary):
    graph_name: str
    graph_version: str
    thread_id: str
    checkpoint_ns: str
    current_checkpoint_id: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    display_state: SopQualityDisplayState


class SopQualityCheckEvent(BaseModel):
    check_id: UUID
    sequence: int
    type: str
    node: str | None = None
    checkpoint_id: str | None = None
    task_id: str | None = None
    message: str | None = None
    created_at: datetime | None = None

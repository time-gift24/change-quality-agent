from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    error = "error"
    timeout = "timeout"
    interrupted = "interrupted"


class RunStartResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    status_url: str
    events_url: str


class ActiveRunConflict(BaseModel):
    message: str
    active_run_id: UUID
    status_url: str
    events_url: str


class RunSummary(BaseModel):
    run_id: UUID
    subject_type: str
    subject_id: str
    status: RunStatus
    current_node: str | None = None
    completed_nodes: list[str]
    latest_sequence: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_status: str | None = None
    error_summary: str | None = None


class RunDebug(BaseModel):
    thread_id: str
    current_checkpoint_id: str | None = None
    langgraph_state_snapshot: dict[str, Any] | None = None
    raw_graph_output: dict[str, Any] | None = None
    raw_last_event: dict[str, Any] | None = None


class RunDetail(RunSummary):
    debug: RunDebug | None = None

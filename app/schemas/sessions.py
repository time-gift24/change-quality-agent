from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

SessionStatus = Literal["active", "completed", "failed", "interrupted"]
MessageRole = Literal["user", "assistant", "tool", "system"]


class SessionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: str
    status: SessionStatus
    title: str | None
    latest_sequence: int
    created_at: datetime
    updated_at: datetime


class SessionMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: int
    sequence: int
    role: MessageRole
    content: str
    additional_kwargs: dict[str, Any]
    created_at: datetime

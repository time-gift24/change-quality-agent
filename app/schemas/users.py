from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: UUID
    account: str
    is_admin: bool
    meta: dict[str, Any] = Field(default_factory=dict)


class DevLoginRequest(BaseModel):
    account: str

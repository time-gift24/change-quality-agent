from uuid import UUID

from pydantic import BaseModel, Field

from app.core.json_types import JsonObject


class UserPublic(BaseModel):
    id: UUID
    account: str
    is_admin: bool
    meta: JsonObject = Field(default_factory=dict)


class DevLoginRequest(BaseModel):
    account: str

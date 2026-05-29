from datetime import datetime

from pydantic import BaseModel

from app.core.json_types import JsonObject


class EnvironmentPublic(BaseModel):
    key: str
    name_zh: str
    name_en: str


class SopSnapshot(BaseModel):
    sop_id: str
    env_key: str
    source_version: str | None = None
    updated_at: datetime | None = None
    payload: JsonObject

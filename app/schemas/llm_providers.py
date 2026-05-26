from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LlmProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str = Field(min_length=1)
    model: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LlmProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_active: bool | None = None


class LlmProviderDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider: str | None
    base_url: str | None
    api_key_hint: str
    model: str | None
    metadata: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

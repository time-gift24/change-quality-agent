from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class AgentDraftConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    system_prompt: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_parameters: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("model_config", "model_parameters"),
        serialization_alias="model_config",
    )
    tool_allowlist: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)


class AgentCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=1)
    description: str | None = None
    draft: AgentDraftConfig


class AgentDraftUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    enabled: bool | None = None
    draft: AgentDraftConfig | None = None


class AgentVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    model: str
    published_at: datetime


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    display_name: str
    description: str | None = None
    enabled: bool
    has_draft: bool
    latest_version: AgentVersionSummary | None = None
    created_at: datetime
    updated_at: datetime


class AgentDetail(AgentSummary):
    draft: AgentDraftConfig | None = None


class AgentVersionDetail(AgentVersionSummary):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    agent_id: UUID
    system_prompt: str
    model_parameters: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("model_config", "model_parameters"),
        serialization_alias="model_config",
    )
    tool_allowlist: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    published_by: str | None = None


class AgentMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant|system)$")
    content: str = Field(min_length=1)


class AgentTestRunCreate(BaseModel):
    version_id: UUID | None = None
    version_number: int | None = Field(default=None, ge=1)
    messages: list[AgentMessage] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_multiple_version_selectors(self) -> "AgentTestRunCreate":
        if self.version_id is not None and self.version_number is not None:
            raise ValueError("Provide either version_id or version_number, not both.")
        return self

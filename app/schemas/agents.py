from datetime import datetime
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

from app.core.llm_model_config import (
    LlmModelParameters,
    dump_llm_model_parameters,
)


class AgentDraftConfig(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        json_schema_mode_override="validation",
    )

    system_prompt: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider_id: UUID | None = None
    model_parameters: LlmModelParameters = Field(
        default_factory=LlmModelParameters,
        validation_alias=AliasChoices("model_config", "model_parameters"),
        serialization_alias="model_config",
    )
    tool_allowlist: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_provider_model_pair(self) -> "AgentDraftConfig":
        if self.provider_id is not None and ":" in self.model:
            raise ValueError("provider_id requires bare model name")
        return self

    @field_serializer("model_parameters")
    def serialize_model_parameters(
        self,
        value: LlmModelParameters,
    ) -> dict[str, object]:
        return dump_llm_model_parameters(value)


class AgentCreate(BaseModel):
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
    provider_id: UUID | None = None
    published_at: datetime


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    description: str | None = None
    enabled: bool
    has_draft: bool
    latest_version: AgentVersionSummary | None = None
    created_at: datetime
    updated_at: datetime


class AgentDetail(AgentSummary):
    draft: AgentDraftConfig | None = None


class BuiltinAgentToolCapability(BaseModel):
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str | None = None
    enabled: bool = True


class McpAgentCapability(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    enabled: bool
    runtime_status: str
    tool_count: int = Field(ge=0)


class AgentCapabilities(BaseModel):
    builtin_tools: list[BuiltinAgentToolCapability] = Field(default_factory=list)
    mcp_servers: list[McpAgentCapability] = Field(default_factory=list)


class AgentSessionStart(BaseModel):
    message: str = Field(min_length=1)
    session_id: int | None = Field(default=None, ge=1)


class AgentSessionStartResponse(BaseModel):
    session_id: int
    stream_url: str


class AgentVersionDetail(AgentVersionSummary):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
        json_schema_mode_override="validation",
    )

    agent_id: UUID
    system_prompt: str
    model_parameters: LlmModelParameters = Field(
        default_factory=LlmModelParameters,
        validation_alias=AliasChoices("model_config", "model_parameters"),
        serialization_alias="model_config",
    )
    tool_allowlist: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    published_by: str | None = None

    @field_serializer("model_parameters")
    def serialize_model_parameters(
        self,
        value: LlmModelParameters,
    ) -> dict[str, object]:
        return dump_llm_model_parameters(value)

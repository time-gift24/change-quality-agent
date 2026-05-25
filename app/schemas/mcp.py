from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_serializer,
    model_validator,
)


REDACTED = "********"
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


class McpTransport(StrEnum):
    stdio = "stdio"
    http = "http"


class McpDesiredState(StrEnum):
    running = "running"
    stopped = "stopped"


class McpServerRuntimeStatus(StrEnum):
    unknown = "unknown"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    stopped = "stopped"
    error = "error"


class McpServerTool(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    input_schema: dict = Field(default_factory=dict)
    discovered_at: datetime | None = None


class McpServerCreate(BaseModel):
    name: str
    transport: McpTransport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False
    desired_state: McpDesiredState = McpDesiredState.stopped

    @model_validator(mode="after")
    def validate_transport_fields(self):
        if self.transport == McpTransport.stdio:
            if not self.command or not self.command.strip():
                raise ValueError("stdio MCP servers require command")
        if self.transport == McpTransport.http:
            if not self.url or not self.url.strip():
                raise ValueError("http MCP servers require url")
            try:
                self.url = str(_HTTP_URL_ADAPTER.validate_python(self.url))
            except ValueError as exc:
                raise ValueError("http MCP servers require valid url") from exc
        return self


class McpServerUpdate(BaseModel):
    name: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    enabled: bool | None = None
    desired_state: McpDesiredState | None = None


class McpServerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    transport: McpTransport
    command: str | None
    args: list[str]
    env: dict[str, str]
    url: str | None
    headers: dict[str, str]
    enabled: bool
    desired_state: McpDesiredState
    runtime_status: McpServerRuntimeStatus
    last_checked_at: datetime | None
    last_error: str | None
    tool_count: int = 0

    @field_serializer("env", "headers")
    def redact_mapping(self, value: dict[str, str]) -> dict[str, str]:
        return {key: REDACTED for key in value}


class McpServerDetail(McpServerSummary):
    tools: list[McpServerTool] = Field(default_factory=list)


class McpLifecycleResponse(BaseModel):
    server_id: UUID
    desired_state: McpDesiredState
    runtime_status: McpServerRuntimeStatus
    last_checked_at: datetime | None
    last_error: str | None
    tool_count: int

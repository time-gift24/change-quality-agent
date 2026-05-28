from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.llm_provider_types import LlmProviderType


REDACTED = "********"
_SECRET_KEY_PARTS = (
    "key",
    "token",
    "secret",
    "authorization",
    "password",
    "credential",
)


def _mask_mapping(value: dict[str, str]) -> dict[str, str]:
    return {
        key: REDACTED if _is_secret_key(key) else mapping_value
        for key, mapping_value in value.items()
    }


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SECRET_KEY_PARTS)


class LlmProviderCreate(BaseModel):
    display_name: str
    description: str | None = None
    provider_type: LlmProviderType
    base_url: str | None = None
    api_key: str | None = None
    default_headers: dict[str, str] = Field(default_factory=dict)
    default_query: dict[str, str] = Field(default_factory=dict)
    models: list[str] = Field(
        default_factory=list,
        description="Model names this provider can serve.",
    )
    enabled: bool = True

    @field_validator("models")
    @classmethod
    def normalize_models(cls, value: list[str]) -> list[str]:
        return _normalize_models(value)


class LlmProviderUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    provider_type: LlmProviderType | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_headers: dict[str, str] | None = None
    default_query: dict[str, str] | None = None
    models: list[str] | None = Field(
        default=None,
        description="Model names this provider can serve.",
    )
    enabled: bool | None = None

    @field_validator("models")
    @classmethod
    def normalize_models(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_models(value)


class LlmProviderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    description: str | None
    provider_type: str
    base_url: str | None
    default_headers: dict[str, str]
    default_query: dict[str, str]
    models: list[str] = Field(default_factory=list)
    enabled: bool
    created_at: datetime
    updated_at: datetime
    api_key_configured: bool = False

    @model_validator(mode="before")
    @classmethod
    def derive_api_key_configured(cls, data: Any) -> Any:
        if isinstance(data, dict):
            values = dict(data)
            values["api_key_configured"] = bool(values.get("api_key"))
            values.pop("api_key", None)
            return values

        if hasattr(data, "api_key") and not hasattr(data, "api_key_configured"):
            return {
                field_name: getattr(data, field_name)
                for field_name in cls.model_fields
                if field_name != "api_key_configured" and hasattr(data, field_name)
            } | {"api_key_configured": bool(getattr(data, "api_key"))}

        return data

    @field_serializer("default_headers", "default_query")
    def mask_secret_values(self, value: dict[str, str]) -> dict[str, str]:
        return _mask_mapping(value)


class LlmProviderDetail(LlmProviderSummary):
    pass


class LlmProviderModelTestRequest(BaseModel):
    model: str = Field(min_length=1)


class LlmProviderModelTestResponse(BaseModel):
    status: Literal["ok", "failed"]
    latency_ms: float
    message: str | None = None
    error: str | None = None
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None


def _normalize_models(value: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        model = item.strip()
        if not model or model in seen:
            continue
        normalized.append(model)
        seen.add(model)
    return normalized

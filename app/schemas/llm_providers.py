from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


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
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str
    description: str | None = None
    provider_type: str
    base_url: str | None = None
    api_key: str | None = None
    default_headers: dict[str, str] = Field(default_factory=dict)
    default_query: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class LlmProviderUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_headers: dict[str, str] | None = None
    default_query: dict[str, str] | None = None
    enabled: bool | None = None


class LlmProviderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    display_name: str
    description: str | None
    provider_type: str
    base_url: str | None
    default_headers: dict[str, str]
    default_query: dict[str, str]
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

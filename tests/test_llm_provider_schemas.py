from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
    LlmProviderUpdate,
)
from app.services.provider_credentials import api_key_hint, prepare_api_key


def test_llm_provider_create_accepts_provider_payload():
    payload = LlmProviderCreate(
        name="Personal OpenAI",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test123456",
        model="gpt-4.1-mini",
        metadata={"team": "quality"},
    )

    assert payload.name == "Personal OpenAI"
    assert payload.provider == "openai"
    assert payload.base_url == "https://api.openai.com/v1"
    assert payload.api_key == "sk-test123456"
    assert payload.model == "gpt-4.1-mini"
    assert payload.metadata == {"team": "quality"}


def test_llm_provider_update_allows_partial_payload():
    payload = LlmProviderUpdate(name="Renamed provider")

    assert payload.name == "Renamed provider"
    assert payload.provider is None
    assert payload.base_url is None
    assert payload.api_key is None
    assert payload.model is None
    assert payload.metadata == {}
    assert payload.is_active is None


def test_llm_provider_update_metadata_exclude_unset_semantics():
    assert "metadata" not in LlmProviderUpdate(model="gpt-4.1-mini").model_dump(
        exclude_unset=True
    )
    assert LlmProviderUpdate(metadata={}).model_dump(exclude_unset=True)[
        "metadata"
    ] == {}


@pytest.mark.parametrize(
    ("schema_cls", "field_name", "payload"),
    [
        (LlmProviderCreate, "name", {"name": " ", "api_key": "sk-test123456"}),
        (
            LlmProviderCreate,
            "provider",
            {"name": "Personal OpenAI", "provider": " ", "api_key": "sk-test123456"},
        ),
        (
            LlmProviderCreate,
            "base_url",
            {"name": "Personal OpenAI", "base_url": " ", "api_key": "sk-test123456"},
        ),
        (LlmProviderCreate, "api_key", {"name": "Personal OpenAI", "api_key": " "}),
        (
            LlmProviderCreate,
            "model",
            {"name": "Personal OpenAI", "model": " ", "api_key": "sk-test123456"},
        ),
        (LlmProviderUpdate, "name", {"name": " "}),
        (LlmProviderUpdate, "provider", {"provider": " "}),
        (LlmProviderUpdate, "base_url", {"base_url": " "}),
        (LlmProviderUpdate, "api_key", {"api_key": " "}),
        (LlmProviderUpdate, "model", {"model": " "}),
    ],
)
def test_llm_provider_input_rejects_whitespace_only_strings(
    schema_cls, field_name, payload
):
    with pytest.raises(ValidationError) as exc_info:
        schema_cls(**payload)

    assert exc_info.value.errors()[0]["loc"] == (field_name,)


def test_llm_provider_detail_does_not_expose_real_keys():
    detail = LlmProviderDetail(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Personal OpenAI",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key_hint="sk-...3456",
        model="gpt-4.1-mini",
        metadata={"team": "quality"},
        is_active=True,
        created_at=datetime(2026, 5, 26, tzinfo=UTC),
        updated_at=datetime(2026, 5, 26, tzinfo=UTC),
    )

    dumped = detail.model_dump()

    assert "api_key" not in dumped
    assert "api_key_ciphertext" not in dumped
    assert dumped["api_key_hint"] == "sk-...3456"


def test_api_key_hint_masks_long_and_short_secrets():
    assert api_key_hint("sk-test123456") == "sk-...3456"
    assert api_key_hint("short") == "********"


def test_prepare_api_key_returns_replaceable_ciphertext_and_hint():
    prepared = prepare_api_key("sk-test123456")

    assert prepared.ciphertext == "sk-test123456"
    assert prepared.hint == "sk-...3456"

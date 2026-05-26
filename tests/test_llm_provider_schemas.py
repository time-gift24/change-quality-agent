from datetime import UTC, datetime
from uuid import UUID

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

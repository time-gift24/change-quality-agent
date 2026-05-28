from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.llm_providers import (
    LlmProviderCreate,
    LlmProviderDetail,
    LlmProviderUpdate,
)


def test_detail_masks_secret_like_values_and_reports_api_key_configured() -> None:
    detail = LlmProviderDetail.model_validate(
        SimpleNamespace(
            id=uuid4(),
            display_name="OpenAI",
            description=None,
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-secret",
            default_headers={
                "Authorization": "Bearer secret",
                "X-Tenant": "quality",
            },
            default_query={
                "api-version": "2026-01-01",
                "token": "secret",
            },
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )

    body = detail.model_dump(mode="json")

    assert body["api_key_configured"] is True
    assert "api_key" not in body
    assert body["default_headers"] == {
        "Authorization": "********",
        "X-Tenant": "quality",
    }
    assert body["default_query"] == {
        "api-version": "2026-01-01",
        "token": "********",
    }


def test_detail_reports_missing_api_key() -> None:
    detail = LlmProviderDetail.model_validate(
        SimpleNamespace(
            id=uuid4(),
            display_name="OpenAI",
            description=None,
            provider_type="openai",
            base_url=None,
            api_key=None,
            default_headers={},
            default_query={},
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )

    assert detail.api_key_configured is False


def test_update_distinguishes_omitted_and_null_api_key() -> None:
    omitted = LlmProviderUpdate(display_name="OpenAI")
    cleared = LlmProviderUpdate(api_key=None)

    assert "api_key" not in omitted.model_fields_set
    assert "api_key" in cleared.model_fields_set


def test_create_rejects_unsupported_provider_type() -> None:
    try:
        LlmProviderCreate(display_name="Unsupported", provider_type="custom")
    except ValueError as exc:
        assert "provider_type" in str(exc)
        return

    raise AssertionError("unsupported provider_type should fail validation")


def test_create_normalizes_models() -> None:
    provider = LlmProviderCreate(
        display_name="OpenAI",
        provider_type="openai",
        models=[" gpt-5-mini ", "gpt-5-mini", "", "gpt-5"],
    )

    assert provider.models == ["gpt-5-mini", "gpt-5"]

from uuid import uuid4

from app.schemas.sop_quality_checks import (
    SopQualityCheckDetail,
    SopQualityCheckEvent,
    SopQualityCheckStartResponse,
    SopQualityCheckStatus,
)


def test_start_response_uses_check_id_not_run_id() -> None:
    check_id = uuid4()

    payload = SopQualityCheckStartResponse(
        check_id=check_id,
        status=SopQualityCheckStatus.pending,
        created=True,
        status_url=f"/api/sop-quality-checks/{check_id}",
        stream_url=f"/api/sop-quality-checks/{check_id}/stream",
    ).model_dump(mode="json")

    assert payload["check_id"] == str(check_id)
    assert "run_id" not in payload


def test_event_schema_has_no_payload() -> None:
    fields = SopQualityCheckEvent.model_fields

    assert "payload" not in fields
    assert "channel" in fields
    assert "message" in fields


def test_check_detail_exposes_session_id() -> None:
    fields = SopQualityCheckDetail.model_fields

    assert "session_id" in fields

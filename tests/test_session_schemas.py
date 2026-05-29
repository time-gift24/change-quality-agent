from datetime import datetime
from uuid import uuid4

from app.schemas.sessions import SessionDetail, SessionMessage


def test_session_detail_has_required_fields() -> None:
    detail = SessionDetail(
        id=1,
        thread_id="thread-1",
        status="active",
        title=None,
        latest_sequence=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    assert detail.id == 1
    assert detail.thread_id == "thread-1"
    assert detail.status == "active"
    assert detail.latest_sequence == 0


def test_session_message_has_required_fields() -> None:
    message = SessionMessage(
        id=uuid4(),
        session_id=1,
        sequence=1,
        role="assistant",
        content="hello",
        additional_kwargs={"step": "review_sop"},
        created_at=datetime.now(),
    )

    assert message.session_id == 1
    assert message.sequence == 1
    assert message.role == "assistant"
    assert message.content == "hello"
    assert message.additional_kwargs == {"step": "review_sop"}

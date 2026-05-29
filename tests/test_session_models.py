from app.models.sessions import Message, Session


def test_session_model_columns() -> None:
    columns = Session.__table__.columns

    assert Session.__tablename__ == "sessions"
    assert columns["id"].primary_key
    assert columns["thread_id"].nullable is False
    assert columns["status"].nullable is False
    assert "user_id" not in columns


def test_message_model_columns() -> None:
    columns = Message.__table__.columns

    assert Message.__tablename__ == "messages"
    assert columns["id"].primary_key
    assert columns["session_id"].nullable is False
    assert columns["sequence"].nullable is False
    assert columns["role"].nullable is False
    assert columns["content"].nullable is False
    assert columns["additional_kwargs"].nullable is False


def test_message_model_indexes() -> None:
    indexes = {index.name: index for index in Message.__table__.indexes}

    assert indexes["uq_messages_session_sequence"].unique is True
    assert [
        column.name for column in indexes["uq_messages_session_sequence"].columns
    ] == ["session_id", "sequence"]
    assert [
        column.name for column in indexes["ix_messages_session_created_at"].columns
    ] == ["session_id", "created_at"]

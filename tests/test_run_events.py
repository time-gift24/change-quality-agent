from app.services.run_events import normalize_langgraph_chunk


def test_message_event_extracts_node_from_metadata() -> None:
    event = normalize_langgraph_chunk(
        chunk_type="messages",
        chunk=("hello", {"langgraph_node": "review"}),
        run_id="run-1",
        thread_id="thread-1",
        sequence=3,
    )

    assert event["type"] == "messages"
    assert event["node"] == "review"
    assert event["payload"]["raw"][0] == "hello"


def test_update_event_extracts_node_from_chunk_key() -> None:
    event = normalize_langgraph_chunk(
        chunk_type="updates",
        chunk={"load_sop": {"status": "ok"}},
        run_id="run-1",
        thread_id="thread-1",
        sequence=4,
    )

    assert event["node"] == "load_sop"
    assert event["payload"]["update"] == {"status": "ok"}


def test_error_event_preserves_run_and_sequence() -> None:
    event = normalize_langgraph_chunk(
        chunk_type="error",
        chunk={"message": "boom"},
        run_id="run-1",
        thread_id="thread-1",
        sequence=5,
    )

    assert event["run_id"] == "run-1"
    assert event["thread_id"] == "thread-1"
    assert event["sequence"] == 5
    assert event["type"] == "error"

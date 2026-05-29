from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.agent_streaming import (
    DeepAgentRunInput,
    DeepAgentRunResult,
    DeepAgentStreamRunner,
)


class RecordingWriter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def append_step_message(
        self,
        *,
        step: str,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ) -> object:
        record = {
            "step": step,
            "role": role,
            "content": content,
            "additional_kwargs": additional_kwargs or {},
        }
        self.calls.append(record)

        class FakeMessage:
            sequence = len(self.calls)

        return FakeMessage()


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(event)


class _FakeMessageWithDelta:
    def __init__(self, content: str = "", reasoning: str = "") -> None:
        self.content = content
        self.additional_kwargs = {}
        if reasoning:
            self.additional_kwargs["reasoning_content"] = reasoning


class StreamingAgent:
    def __init__(self, chunks: list[tuple[str, Any]]) -> None:
        self.chunks = chunks
        self.astream_called_with: tuple[dict[str, Any], list[str]] | None = None

    async def astream(self, payload: object, *, stream_mode: object = None) -> object:
        self.astream_called_with = (payload, list(stream_mode or []))
        for chunk in self.chunks:
            yield chunk


class InvokeOnlyAgent:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.ainvoke = AsyncMock(return_value=response)


@pytest.mark.asyncio
async def test_runner_prefers_astream_and_aggregates_content() -> None:
    chunks = [
        (
            "messages",
            (_FakeMessageWithDelta(content="Hello "), {"langgraph_node": "review_sop"}),
        ),
        (
            "messages",
            (_FakeMessageWithDelta(content="World"), {"langgraph_node": "review_sop"}),
        ),
    ]
    agent = StreamingAgent(chunks)
    writer = RecordingWriter()
    publisher = RecordingPublisher()
    runner = DeepAgentStreamRunner(
        message_writer=writer, live_event_publisher=publisher
    )

    result = await runner.run_step(
        agent=agent,
        step="review_sop",
        input=DeepAgentRunInput(messages=[{"role": "user", "content": "review"}]),
    )

    assert isinstance(result, DeepAgentRunResult)
    assert result.final_text == "Hello World"
    assert agent.astream_called_with is not None
    payload, stream_mode = agent.astream_called_with
    assert payload == {"messages": [{"role": "user", "content": "review"}]}
    assert "messages" in stream_mode


@pytest.mark.asyncio
async def test_runner_broadcasts_live_message_delta() -> None:
    chunks = [
        (
            "messages",
            (_FakeMessageWithDelta(content="abc"), {"langgraph_node": "review_sop"}),
        ),
    ]
    agent = StreamingAgent(chunks)
    writer = RecordingWriter()
    publisher = RecordingPublisher()
    runner = DeepAgentStreamRunner(
        message_writer=writer, live_event_publisher=publisher
    )

    await runner.run_step(
        agent=agent,
        step="review_sop",
        input=DeepAgentRunInput(messages=[]),
    )

    delta_events = [e for e in publisher.events if e.get("type") == "message_delta"]
    assert delta_events, "expected at least one message_delta live event"
    assert delta_events[0]["additional_kwargs"]["channel"] == "content"
    assert delta_events[0]["content"] == "abc"
    assert delta_events[0]["sequence"] is None


@pytest.mark.asyncio
async def test_runner_emits_thinking_status_without_text() -> None:
    chunks = [
        (
            "messages",
            (
                _FakeMessageWithDelta(reasoning="private thoughts"),
                {"langgraph_node": "review_sop"},
            ),
        ),
        (
            "messages",
            (
                _FakeMessageWithDelta(content="visible"),
                {"langgraph_node": "review_sop"},
            ),
        ),
    ]
    agent = StreamingAgent(chunks)
    writer = RecordingWriter()
    publisher = RecordingPublisher()
    runner = DeepAgentStreamRunner(
        message_writer=writer, live_event_publisher=publisher
    )

    await runner.run_step(
        agent=agent,
        step="review_sop",
        input=DeepAgentRunInput(messages=[]),
    )

    thinking_events = [
        e
        for e in publisher.events
        if e.get("type") == "message_delta"
        and e.get("additional_kwargs", {}).get("channel") == "thinking"
    ]
    assert thinking_events, "expected a thinking live event"
    for event in thinking_events:
        assert "private thoughts" not in event.get("content", "")


@pytest.mark.asyncio
async def test_runner_persists_exactly_one_final_assistant_message() -> None:
    chunks = [
        (
            "messages",
            (_FakeMessageWithDelta(content="hello"), {"langgraph_node": "review_sop"}),
        ),
        (
            "messages",
            (_FakeMessageWithDelta(content=" world"), {"langgraph_node": "review_sop"}),
        ),
    ]
    agent = StreamingAgent(chunks)
    writer = RecordingWriter()
    publisher = RecordingPublisher()
    runner = DeepAgentStreamRunner(
        message_writer=writer, live_event_publisher=publisher
    )

    await runner.run_step(
        agent=agent,
        step="review_sop",
        input=DeepAgentRunInput(messages=[]),
    )

    assistant_messages = [
        c
        for c in writer.calls
        if c["role"] == "assistant"
        and c["additional_kwargs"].get("kind") == "final_message"
    ]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["content"] == "hello world"
    assert assistant_messages[0]["step"] == "review_sop"
    assert assistant_messages[0]["additional_kwargs"]["step"] == "review_sop"


@pytest.mark.asyncio
async def test_runner_falls_back_to_ainvoke_when_no_astream() -> None:
    agent = InvokeOnlyAgent(
        {"messages": [{"role": "assistant", "content": "fallback text"}]}
    )
    writer = RecordingWriter()
    publisher = RecordingPublisher()
    runner = DeepAgentStreamRunner(
        message_writer=writer, live_event_publisher=publisher
    )

    result = await runner.run_step(
        agent=agent,
        step="review_sop",
        input=DeepAgentRunInput(messages=[]),
    )

    assert result.final_text == "fallback text"
    agent.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_runner_writes_final_message_for_ainvoke_path() -> None:
    agent = InvokeOnlyAgent(
        {"messages": [{"role": "assistant", "content": "fallback"}]}
    )
    writer = RecordingWriter()
    publisher = RecordingPublisher()
    runner = DeepAgentStreamRunner(
        message_writer=writer, live_event_publisher=publisher
    )

    await runner.run_step(
        agent=agent,
        step="review_sop",
        input=DeepAgentRunInput(messages=[]),
    )

    assistant_messages = [c for c in writer.calls if c["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["content"] == "fallback"

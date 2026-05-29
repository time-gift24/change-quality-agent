from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.services.session_messages import RepositorySessionMessageWriter


class FakeMessage:
    def __init__(
        self,
        session_id: int,
        sequence: int,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any],
    ) -> None:
        self.id = uuid4()
        self.session_id = session_id
        self.sequence = sequence
        self.role = role
        self.content = content
        self.additional_kwargs = additional_kwargs
        self.created_at = datetime.now(UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.appended: list[FakeMessage] = []
        self.commits = 0

    async def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ) -> FakeMessage:
        sequence = len(self.appended) + 1
        message = FakeMessage(
            session_id=session_id,
            sequence=sequence,
            role=role,
            content=content,
            additional_kwargs=additional_kwargs or {},
        )
        self.appended.append(message)
        return message

    async def commit(self) -> None:
        self.commits += 1


class FakeBroadcast:
    def __init__(self, repository: FakeRepository | None = None) -> None:
        self._repository = repository
        self.published: list[tuple[int, dict[str, Any]]] = []

    async def publish(self, session_id: int, message: dict[str, Any]) -> None:
        if self._repository is not None:
            assert self._repository.commits == 1
        self.published.append((session_id, message))


@pytest.mark.asyncio
async def test_writer_appends_persisted_message_with_step_metadata() -> None:
    repo = FakeRepository()
    broadcast = FakeBroadcast()
    writer = RepositorySessionMessageWriter(
        repository=repo,
        session_id=42,
        broadcast=broadcast,
    )

    message = await writer.append_step_message(
        step="review_sop",
        role="assistant",
        content="hello",
        additional_kwargs={"kind": "final_message"},
    )

    assert message.sequence == 1
    assert repo.appended[0].session_id == 42
    assert repo.appended[0].role == "assistant"
    assert repo.appended[0].content == "hello"
    assert repo.appended[0].additional_kwargs["step"] == "review_sop"
    assert repo.appended[0].additional_kwargs["kind"] == "final_message"


@pytest.mark.asyncio
async def test_writer_publishes_persisted_message_event() -> None:
    repo = FakeRepository()
    broadcast = FakeBroadcast()
    writer = RepositorySessionMessageWriter(
        repository=repo,
        session_id=7,
        broadcast=broadcast,
    )

    await writer.append_step_message(
        step="load_sop",
        role="system",
        content="SOP loaded.",
    )

    assert len(broadcast.published) == 1
    session_id, event = broadcast.published[0]
    assert session_id == 7
    assert event["type"] == "message"
    assert event["content"] == "SOP loaded."
    assert event["additional_kwargs"]["step"] == "load_sop"


@pytest.mark.asyncio
async def test_writer_commits_before_publishing_persisted_message() -> None:
    repo = FakeRepository()
    broadcast = FakeBroadcast(repository=repo)
    writer = RepositorySessionMessageWriter(
        repository=repo,
        session_id=7,
        broadcast=broadcast,
        commit=repo.commit,
    )

    await writer.append_step_message(
        step="load_sop",
        role="system",
        content="SOP loaded.",
    )

    assert repo.commits == 1
    assert len(broadcast.published) == 1


@pytest.mark.asyncio
async def test_writer_does_not_publish_token_deltas() -> None:
    repo = FakeRepository()
    broadcast = FakeBroadcast()
    writer = RepositorySessionMessageWriter(
        repository=repo,
        session_id=7,
        broadcast=broadcast,
    )

    await writer.append_step_message(
        step="review_sop",
        role="assistant",
        content="final",
        additional_kwargs={"kind": "final_message"},
    )

    for _, event in broadcast.published:
        assert event["type"] != "message_delta"


@pytest.mark.asyncio
async def test_writer_works_without_broadcast() -> None:
    repo = FakeRepository()
    writer = RepositorySessionMessageWriter(
        repository=repo,
        session_id=1,
        broadcast=None,
    )

    message = await writer.append_step_message(
        step="load_sop",
        role="system",
        content="ok",
    )

    assert message.sequence == 1

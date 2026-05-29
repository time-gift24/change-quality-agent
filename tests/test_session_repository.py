import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.sessions import SessionRepository

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.db,
    pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"),
        reason="set TEST_DATABASE_URL to run repository integration tests",
    ),
]


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


async def test_create_session_sets_status_active(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    assert runtime_session.status == "active"
    assert runtime_session.thread_id
    assert runtime_session.id is not None


async def test_create_session_accepts_custom_thread_id(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session(thread_id="custom-thread-123")

    assert runtime_session.thread_id == "custom-thread-123"


async def test_append_message_assigns_session_local_sequence(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    first = await repository.append_message(
        runtime_session.id,
        role="user",
        content="hello",
    )
    second = await repository.append_message(
        runtime_session.id,
        role="assistant",
        content="world",
    )

    assert first.sequence == 1
    assert second.sequence == 2


async def test_get_messages_after_returns_only_later_messages(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    await repository.append_message(runtime_session.id, role="user", content="first")
    await repository.append_message(runtime_session.id, role="assistant", content="second")
    await repository.append_message(runtime_session.id, role="user", content="third")

    messages = await repository.get_messages_after(runtime_session.id, after=1)

    assert [m.sequence for m in messages] == [2, 3]


async def test_latest_sequence_returns_zero_when_no_messages(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    assert await repository.latest_sequence(runtime_session.id) == 0


async def test_latest_sequence_returns_max_sequence(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    await repository.append_message(runtime_session.id, role="user", content="hello")
    await repository.append_message(runtime_session.id, role="assistant", content="world")

    assert await repository.latest_sequence(runtime_session.id) == 2


async def test_set_status_updates_session(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    updated = await repository.set_status(runtime_session.id, "completed")

    assert updated.status == "completed"


async def test_get_session_returns_latest_sequence(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    await repository.append_message(runtime_session.id, role="user", content="hello")

    fetched = await repository.get_session(runtime_session.id)

    assert fetched is not None
    assert fetched.latest_sequence == 1


async def test_get_session_by_thread_id(session) -> None:
    repository = SessionRepository(session)
    await repository.create_session(thread_id="thread-abc")

    fetched = await repository.get_session_by_thread_id("thread-abc")

    assert fetched is not None
    assert fetched.thread_id == "thread-abc"

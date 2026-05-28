import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.sop_quality_checks import (
    ActiveSopQualityCheckExistsError,
    SopQualityCheckRepository,
)

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


async def test_create_check_persists_business_fields(session) -> None:
    repository = SopQualityCheckRepository(session)

    check = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist", "payload": {}},
    )

    assert check.sop_id == "release-checklist"
    assert check.env_key == "dev"
    assert check.status == "pending"
    assert check.thread_id
    assert check.checkpoint_ns == ""


async def test_duplicate_active_check_returns_active_id(session) -> None:
    repository = SopQualityCheckRepository(session)
    first = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )

    with pytest.raises(ActiveSopQualityCheckExistsError) as exc_info:
        await repository.create_check(
            sop_id="release-checklist",
            env_key="dev",
            graph_name="sop_quality",
            graph_version="sop-quality@1",
            sop_snapshot={"sop_id": "release-checklist"},
        )

    assert exc_info.value.active_check_id == first.id


async def test_terminal_check_does_not_block_new_check(session) -> None:
    repository = SopQualityCheckRepository(session)
    first = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )
    await repository.mark_terminal(first.id, "succeeded", quality_result="pass", result={})

    second = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )

    assert second.id != first.id


async def test_append_event_increments_sequence_without_payload(session) -> None:
    repository = SopQualityCheckRepository(session)
    check = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )

    first = await repository.append_event(check.id, event_type="created")
    second = await repository.append_event(
        check.id,
        event_type="checkpoint",
        node="check_steps",
        checkpoint_id="checkpoint-1",
        message="Checkpoint saved.",
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert not hasattr(second, "payload")


async def test_interrupt_active_checks_on_startup(session) -> None:
    repository = SopQualityCheckRepository(session)
    check = await repository.create_check(
        sop_id="release-checklist",
        env_key="dev",
        graph_name="sop_quality",
        graph_version="sop-quality@1",
        sop_snapshot={"sop_id": "release-checklist"},
    )
    await repository.mark_running(check.id)

    interrupted = await repository.interrupt_active_checks_on_startup()

    assert [item.id for item in interrupted] == [check.id]
    assert interrupted[0].status == "interrupted"
    events = await repository.get_events_after(check.id)
    assert events[-1].type == "interrupted"

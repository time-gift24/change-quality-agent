import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repositories.runs import ActiveRunExistsError, RunRepository
from app.schemas.runs import RunStatus

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


async def test_create_run_persists_sop_metadata(session) -> None:
    repository = RunRepository(session)

    run = await repository.create_sop_run(
        sop_id="release-checklist",
        env_key="dev",
        env_snapshot={"key": "dev", "name_zh": "开发", "name_en": "Development"},
        sop_snapshot={"sop_id": "release-checklist", "payload": {}},
        active_conflict_key="sop:release-checklist:env:dev",
    )

    assert run.metadata_["subject_type"] == "sop"
    assert run.metadata_["subject_id"] == "release-checklist"
    assert run.metadata_["env_key"] == "dev"


async def test_active_conflict_key_rejects_duplicate_active_run(session) -> None:
    repository = RunRepository(session)
    run = await repository.create_sop_run(
        sop_id="release-checklist",
        env_key="dev",
        env_snapshot={"key": "dev", "name_zh": "开发", "name_en": "Development"},
        sop_snapshot={"sop_id": "release-checklist", "payload": {}},
        active_conflict_key="sop:release-checklist:env:dev",
    )

    with pytest.raises(ActiveRunExistsError) as exc_info:
        await repository.create_sop_run(
            sop_id="release-checklist",
            env_key="dev",
            env_snapshot={"key": "dev", "name_zh": "开发", "name_en": "Development"},
            sop_snapshot={"sop_id": "release-checklist", "payload": {}},
            active_conflict_key="sop:release-checklist:env:dev",
        )

    assert exc_info.value.active_run_id == run.id


async def test_terminal_run_does_not_block_new_run(session) -> None:
    repository = RunRepository(session)
    first_run = await repository.create_sop_run(
        sop_id="release-checklist",
        env_key="dev",
        env_snapshot={"key": "dev", "name_zh": "开发", "name_en": "Development"},
        sop_snapshot={"sop_id": "release-checklist", "payload": {}},
        active_conflict_key="sop:release-checklist:env:dev",
    )
    await repository.mark_terminal(first_run.id, RunStatus.success)

    second_run = await repository.create_sop_run(
        sop_id="release-checklist",
        env_key="dev",
        env_snapshot={"key": "dev", "name_zh": "开发", "name_en": "Development"},
        sop_snapshot={"sop_id": "release-checklist", "payload": {}},
        active_conflict_key="sop:release-checklist:env:dev",
    )

    assert second_run.id != first_run.id


async def test_append_event_increments_sequence(session) -> None:
    repository = RunRepository(session)
    run = await repository.create_sop_run(
        sop_id="release-checklist",
        env_key="dev",
        env_snapshot={"key": "dev", "name_zh": "开发", "name_en": "Development"},
        sop_snapshot={"sop_id": "release-checklist", "payload": {}},
        active_conflict_key="sop:release-checklist:env:dev",
    )

    first_event = await repository.append_event(
        run.id,
        event_type="custom",
        thread_id=run.thread_id,
        payload={"message": "first"},
    )
    second_event = await repository.append_event(
        run.id,
        event_type="custom",
        thread_id=run.thread_id,
        payload={"message": "second"},
    )

    assert first_event.sequence == 1
    assert second_event.sequence == 2

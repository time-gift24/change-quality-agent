import os
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.users  # noqa: F401
from app.core.database import Base

requires_test_database = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL to run repository integration tests",
)


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


def repository_types() -> Any:
    try:
        from app.repositories import users
    except ModuleNotFoundError as exc:
        pytest.fail(f"User repository module is missing: {exc}")
    return users


def test_user_repository_module_defines_expected_public_api() -> None:
    users = repository_types()

    assert users.UserRepository is not None
    assert users.DEV_USERS is not None
    assert users.seed_dev_users is not None


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_upsert_user_creates_and_updates_user(session) -> None:
    users = repository_types()
    repository = users.UserRepository(session)

    created = await repository.upsert_user(
        account="common",
        refresh_token="token-1",
        is_admin=False,
        meta={"source": "test"},
    )
    updated = await repository.upsert_user(
        account="common",
        refresh_token="token-2",
        is_admin=True,
        meta={"source": "updated"},
    )

    assert created.id == updated.id
    assert updated.refresh_token == "token-2"
    assert updated.is_admin is True

import os
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.users  # noqa: F401
from app.core.database import Base

requires_test_database = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL to run repository integration tests",
)


@pytest_asyncio.fixture
async def session() -> object:
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
    assert users.DEV_USER_ACCOUNTS is not None
    assert users.dev_users_from_settings is not None
    assert users.seed_dev_users is not None


class FakeResult:
    def __init__(self, user: Any) -> None:
        self._user = user

    def scalar_one(self) -> Any:
        return self._user


class RecordingSession:
    def __init__(self) -> None:
        self.flushes = 0
        self.params: list[dict[str, Any]] = []
        self.sql: list[str] = []
        self.returned_user = SimpleNamespace(id="user-id")

    async def execute(self, statement: Any) -> FakeResult:
        compiled = statement.compile(dialect=postgresql.dialect())
        self.params.append(compiled.params)
        self.sql.append(str(compiled))
        return FakeResult(self.returned_user)

    async def flush(self) -> None:
        self.flushes += 1


@pytest.mark.asyncio
async def test_upsert_user_uses_atomic_returning_statement_and_copies_meta() -> None:
    users = repository_types()
    session = RecordingSession()
    repository = users.UserRepository(session)
    meta = {"source": {"name": "test"}}

    user = await repository.upsert_user(
        account="common",
        refresh_token="token-1",
        is_admin=False,
        meta=meta,
    )
    meta["source"]["name"] = "mutated"

    assert user is session.returned_user
    assert len(session.sql) == 1
    assert "ON CONFLICT" in session.sql[0]
    assert "RETURNING" in session.sql[0]
    assert session.params[0]["meta"] == {"source": {"name": "test"}}
    assert session.params[0]["meta"] is not meta
    assert session.params[0]["meta"]["source"] is not meta["source"]
    assert session.flushes == 1


@pytest.mark.asyncio
async def test_seed_dev_users_upserts_expected_users() -> None:
    users = repository_types()
    session = RecordingSession()
    repository = users.UserRepository(session)
    settings = SimpleNamespace(
        auth_dev_common_refresh_token="common-refresh-token",
        auth_dev_admin_refresh_token="admin-refresh-token",
    )

    await users.seed_dev_users(repository, users.dev_users_from_settings(settings))

    assert [params["account"] for params in session.params] == ["common", "admin"]
    assert [params["refresh_token"] for params in session.params] == [
        "common-refresh-token",
        "admin-refresh-token",
    ]
    assert [params["is_admin"] for params in session.params] == [False, True]
    assert [params["meta"] for params in session.params] == [
        {"source": "dev"},
        {"source": "dev"},
    ]
    assert session.flushes == len(users.DEV_USER_ACCOUNTS)


@pytest.mark.asyncio
@pytest.mark.db
@requires_test_database
async def test_upsert_user_creates_and_updates_user(session: object) -> None:
    users = repository_types()
    repository = users.UserRepository(session)

    created = await repository.upsert_user(
        account="common",
        refresh_token="token-1",
        is_admin=False,
        meta={"source": "test"},
    )
    created_by_account = await repository.get_by_account("common")
    assert created_by_account is not None
    assert created_by_account.id == created.id
    assert created_by_account.meta == {"source": "test"}

    updated = await repository.upsert_user(
        account="common",
        refresh_token="token-2",
        is_admin=True,
        meta={"source": "updated"},
    )
    updated_by_account = await repository.get_by_account("common")

    assert created.id == updated.id
    assert updated.refresh_token == "token-2"
    assert updated.is_admin is True
    assert updated.meta == {"source": "updated"}
    assert updated_by_account is not None
    assert updated_by_account.id == updated.id
    assert updated_by_account.meta == {"source": "updated"}

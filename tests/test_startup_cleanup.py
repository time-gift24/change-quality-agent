import pytest

from app import main
from app.core.config import settings
from app.main import interrupt_leftover_sop_quality_checks, seed_dev_users_on_startup


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeRepository:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.interrupted = False

    async def interrupt_active_checks_on_startup(self):
        self.interrupted = True
        return []


class FakeUserRepository:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.seeded = False


@pytest.mark.asyncio
async def test_startup_cleanup_interrupts_leftover_sop_quality_checks(
    monkeypatch,
) -> None:
    session = FakeSession()
    repository = FakeRepository(session)

    monkeypatch.setattr(main, "async_session", lambda: FakeSessionContext(session))
    monkeypatch.setattr(
        main,
        "SopQualityCheckRepository",
        lambda db_session: repository,
    )

    await interrupt_leftover_sop_quality_checks()

    assert repository.interrupted is True
    assert session.committed is True


@pytest.mark.asyncio
async def test_seed_dev_users_on_startup_seeds_and_commits(monkeypatch) -> None:
    session = FakeSession()
    repository = FakeUserRepository(session)

    async def fake_seed_dev_users(user_repository: FakeUserRepository) -> None:
        user_repository.seeded = True

    monkeypatch.setattr(main, "async_session", lambda: FakeSessionContext(session))
    monkeypatch.setattr(main, "UserRepository", lambda db_session: repository)
    monkeypatch.setattr(main, "seed_dev_users", fake_seed_dev_users)

    await seed_dev_users_on_startup()

    assert repository.session is session
    assert repository.seeded is True
    assert session.committed is True


@pytest.mark.asyncio
async def test_lifespan_seeds_dev_users_before_mcp_startup(monkeypatch) -> None:
    events = []

    async def fake_interrupt_leftover_sop_quality_checks() -> None:
        events.append("interrupt")

    async def fake_seed_dev_users_on_startup() -> None:
        events.append("seed")

    class FakeRuntime:
        async def start_enabled_servers(self) -> None:
            events.append("mcp-start")

        async def shutdown(self) -> None:
            events.append("mcp-shutdown")

    monkeypatch.setattr(settings, "auth_dev_mode", True)
    monkeypatch.setattr(
        main,
        "interrupt_leftover_sop_quality_checks",
        fake_interrupt_leftover_sop_quality_checks,
    )
    monkeypatch.setattr(main, "seed_dev_users_on_startup", fake_seed_dev_users_on_startup)
    monkeypatch.setattr(main, "get_mcp_runtime_manager", lambda: FakeRuntime())

    async with main.lifespan(main.app):
        assert events == ["interrupt", "seed", "mcp-start"]

    assert events == ["interrupt", "seed", "mcp-start", "mcp-shutdown"]

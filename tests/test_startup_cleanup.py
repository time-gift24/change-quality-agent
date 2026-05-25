import pytest

from app import main
from app.main import interrupt_leftover_runs


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

    async def interrupt_active_runs_on_startup(self):
        self.interrupted = True
        return []


@pytest.mark.asyncio
async def test_startup_cleanup_interrupts_leftover_runs(monkeypatch) -> None:
    session = FakeSession()
    repository = FakeRepository(session)

    monkeypatch.setattr(main, "async_session", lambda: FakeSessionContext(session))
    monkeypatch.setattr(main, "RunRepository", lambda db_session: repository)

    await interrupt_leftover_runs()

    assert repository.interrupted is True
    assert session.committed is True

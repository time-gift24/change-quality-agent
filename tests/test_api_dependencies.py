from app.api.deps import get_run_repository, get_sop_client
from app.repositories.runs import RunRepository
from app.services.sop_client import MockSopClient


def test_sop_client_dependency_defaults_to_mock() -> None:
    assert isinstance(get_sop_client(), MockSopClient)


def test_run_repository_dependency_uses_session() -> None:
    session = object()

    repository = get_run_repository(session)

    assert isinstance(repository, RunRepository)
    assert repository._session is session

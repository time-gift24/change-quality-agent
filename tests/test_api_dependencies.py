from app.api.deps import (
    get_sop_client,
    get_sop_quality_check_repository,
    get_user_repository,
)
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.repositories.users import UserRepository
from app.services.sop_client import MockSopClient


def test_sop_client_dependency_defaults_to_mock() -> None:
    assert isinstance(get_sop_client(), MockSopClient)


def test_sop_quality_check_repository_dependency_uses_session() -> None:
    session = object()

    repository = get_sop_quality_check_repository(session)

    assert isinstance(repository, SopQualityCheckRepository)
    assert repository._session is session


def test_user_repository_dependency_uses_session() -> None:
    session = object()

    repository = get_user_repository(session)

    assert isinstance(repository, UserRepository)
    assert repository._session is session

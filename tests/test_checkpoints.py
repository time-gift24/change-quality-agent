from app.core.checkpoints import postgres_checkpoint_url


def test_postgres_checkpoint_url_strips_asyncpg_driver() -> None:
    assert postgres_checkpoint_url(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/db"
    ) == "postgresql://postgres:postgres@localhost:5432/db"


def test_postgres_checkpoint_url_leaves_plain_url_unchanged() -> None:
    assert postgres_checkpoint_url("postgresql://localhost/db") == (
        "postgresql://localhost/db"
    )

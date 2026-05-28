from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings


def postgres_checkpoint_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return f"postgresql://{database_url.removeprefix('postgresql+asyncpg://')}"
    if database_url.startswith("postgres+asyncpg://"):
        return f"postgres://{database_url.removeprefix('postgres+asyncpg://')}"
    return database_url


@asynccontextmanager
async def open_postgres_checkpointer(
    database_url: str | None = None,
    *,
    setup: bool = False,
) -> AsyncIterator[AsyncPostgresSaver]:
    checkpoint_url = postgres_checkpoint_url(database_url or settings.database_url)
    async with AsyncPostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
        if setup:
            await checkpointer.setup()
        yield checkpointer

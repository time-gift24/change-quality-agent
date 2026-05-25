from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, get_session
from app.repositories.mcp_servers import McpServerRepository
from app.repositories.runs import RunRepository
from app.services.mcp_runtime import McpRuntimeManager
from app.services.sop_client import MockSopClient, SopClient

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_sop_client() -> SopClient:
    return MockSopClient()


SopClientDep = Annotated[SopClient, Depends(get_sop_client)]


def get_run_repository(session: SessionDep) -> RunRepository:
    return RunRepository(session)


RunRepositoryDep = Annotated[RunRepository, Depends(get_run_repository)]


def get_mcp_repository(session: SessionDep) -> McpServerRepository:
    return McpServerRepository(session)


McpRepositoryDep = Annotated[McpServerRepository, Depends(get_mcp_repository)]


@asynccontextmanager
async def mcp_runtime_repository_context():
    async with async_session() as session:
        yield McpServerRepository(session)


_mcp_runtime_manager: McpRuntimeManager | None = None


def get_mcp_runtime_manager() -> McpRuntimeManager:
    global _mcp_runtime_manager
    if _mcp_runtime_manager is None:
        _mcp_runtime_manager = McpRuntimeManager(
            repository_factory=mcp_runtime_repository_context,
        )
    return _mcp_runtime_manager


McpRuntimeManagerDep = Annotated[
    McpRuntimeManager,
    Depends(get_mcp_runtime_manager),
]

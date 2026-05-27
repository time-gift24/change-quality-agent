from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_session
from app.repositories.agents import AgentRepository
from app.repositories.mcp_servers import McpServerRepository
from app.repositories.runs import RunRepository
from app.repositories.users import UserRepository
from app.services.mcp_runtime import McpRuntimeManager, StdioMcpProbe, TransportMcpProbe
from app.services.sop_client import MockSopClient, SopClient

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_sop_client() -> SopClient:
    return MockSopClient()


SopClientDep = Annotated[SopClient, Depends(get_sop_client)]


def get_run_repository(session: SessionDep) -> RunRepository:
    return RunRepository(session)


RunRepositoryDep = Annotated[RunRepository, Depends(get_run_repository)]


def get_agent_repository(session: SessionDep) -> AgentRepository:
    return AgentRepository(session)


AgentRepositoryDep = Annotated[AgentRepository, Depends(get_agent_repository)]


def get_mcp_repository(session: SessionDep) -> McpServerRepository:
    return McpServerRepository(session)


McpRepositoryDep = Annotated[McpServerRepository, Depends(get_mcp_repository)]


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def require_mcp_admin(
    token: Annotated[str | None, Header(alias="X-MCP-Admin-Token")] = None,
) -> None:
    if not settings.mcp_admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP admin token is not configured.",
        )
    if token is None or not compare_digest(token, settings.mcp_admin_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid MCP admin token.",
        )


McpAdminDep = Annotated[None, Depends(require_mcp_admin)]


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
            operation_timeout_seconds=settings.mcp_operation_timeout_seconds,
            single_instance_confirmed=settings.mcp_runtime_single_instance,
            probe=TransportMcpProbe(
                stdio_probe=StdioMcpProbe(
                    allowed_commands=set(settings.mcp_allowed_stdio_commands),
                    allowed_stdio_specs=set(settings.mcp_allowed_stdio_specs),
                ),
            ),
        )
    return _mcp_runtime_manager


McpRuntimeManagerDep = Annotated[
    McpRuntimeManager,
    Depends(get_mcp_runtime_manager),
]

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_session
from app.repositories.agents import AgentRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.mcp_servers import McpServerRepository
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.repositories.users import UserRepository
from app.services.mcp_runtime import McpRuntimeManager, StdioMcpProbe, TransportMcpProbe
from app.services.sop_client import MockSopClient, SopClient

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_sop_client() -> SopClient:
    return MockSopClient()


SopClientDep = Annotated[SopClient, Depends(get_sop_client)]


def get_sop_quality_check_repository(
    session: SessionDep,
) -> SopQualityCheckRepository:
    return SopQualityCheckRepository(session)


SopQualityCheckRepositoryDep = Annotated[
    SopQualityCheckRepository,
    Depends(get_sop_quality_check_repository),
]


def get_agent_repository(session: SessionDep) -> AgentRepository:
    return AgentRepository(session)


AgentRepositoryDep = Annotated[AgentRepository, Depends(get_agent_repository)]


def get_llm_provider_repository(session: SessionDep) -> LlmProviderRepository:
    return LlmProviderRepository(session)


LlmProviderRepositoryDep = Annotated[
    LlmProviderRepository,
    Depends(get_llm_provider_repository),
]


def get_mcp_repository(session: SessionDep) -> McpServerRepository:
    return McpServerRepository(session)


McpRepositoryDep = Annotated[McpServerRepository, Depends(get_mcp_repository)]


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def require_admin_user(request: Request) -> None:
    if not settings.auth_enabled:
        return

    current_user = getattr(request.state, "current_user", None)
    if current_user is None or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )


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

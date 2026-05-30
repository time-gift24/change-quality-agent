from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_session
from app.repositories.agents import AgentRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.mcp_servers import McpServerRepository
from app.repositories.sessions import SessionRepository
from app.repositories.sop_quality_checks import SopQualityCheckRepository
from app.repositories.users import UserRepository
from app.services.mcp_runtime import McpRuntimeManager, StdioMcpProbe, TransportMcpProbe
from app.services.agents import AgentService
from app.services.agent_capabilities import AgentCapabilityService
from app.services.auth import AuthService
from app.services.llm_providers import LlmProviderService
from app.services.mcp_servers import McpServerService
from app.services.sessions import SessionService
from app.services.session_streaming import SessionBroadcast
from app.services.sop_client import MockSopClient, SopClient
from app.services.sop_quality import SopQualityService
from app.services.sop_quality_runner import run_sop_quality_check_with_new_session
from app.services.sop_quality_streaming import SopQualityBroadcast

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


def get_session_repository(session: SessionDep) -> SessionRepository:
    return SessionRepository(session)


SessionRepositoryDep = Annotated[SessionRepository, Depends(get_session_repository)]


_session_broadcast = SessionBroadcast()


def get_session_broadcast() -> SessionBroadcast:
    return _session_broadcast


SessionBroadcastDep = Annotated[SessionBroadcast, Depends(get_session_broadcast)]


def get_agent_repository(session: SessionDep) -> AgentRepository:
    return AgentRepository(session)


AgentRepositoryDep = Annotated[AgentRepository, Depends(get_agent_repository)]


def get_agent_service(
    session: SessionDep,
    repository: AgentRepositoryDep,
    session_repository: SessionRepositoryDep,
    session_broadcast: SessionBroadcastDep,
) -> AgentService:
    return AgentService(
        repository=repository,
        commit=session.commit,
        session_repository=session_repository,
        session_broadcast=session_broadcast,
    )


AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


def get_llm_provider_repository(session: SessionDep) -> LlmProviderRepository:
    return LlmProviderRepository(session)


LlmProviderRepositoryDep = Annotated[
    LlmProviderRepository,
    Depends(get_llm_provider_repository),
]


def get_llm_provider_service(
    session: SessionDep,
    repository: LlmProviderRepositoryDep,
) -> LlmProviderService:
    return LlmProviderService(repository=repository, commit=session.commit)


LlmProviderServiceDep = Annotated[
    LlmProviderService,
    Depends(get_llm_provider_service),
]


def get_mcp_repository(session: SessionDep) -> McpServerRepository:
    return McpServerRepository(session)


McpRepositoryDep = Annotated[McpServerRepository, Depends(get_mcp_repository)]


def get_agent_capability_service(
    mcp_repository: McpRepositoryDep,
) -> AgentCapabilityService:
    return AgentCapabilityService(mcp_repository=mcp_repository)


AgentCapabilityServiceDep = Annotated[
    AgentCapabilityService,
    Depends(get_agent_capability_service),
]


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_auth_service() -> AuthService:
    return AuthService(settings=settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_dev_auth_service(repository: UserRepositoryDep) -> AuthService:
    return AuthService(settings=settings, repository=repository)


DevAuthServiceDep = Annotated[AuthService, Depends(get_dev_auth_service)]


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


def get_mcp_server_service(
    repository: McpRepositoryDep,
    runtime: McpRuntimeManagerDep,
) -> McpServerService:
    return McpServerService(repository=repository, runtime=runtime)


McpServerServiceDep = Annotated[
    McpServerService,
    Depends(get_mcp_server_service),
]


_sop_quality_broadcast = SopQualityBroadcast()


def get_sop_quality_broadcast() -> SopQualityBroadcast:
    return _sop_quality_broadcast


SopQualityBroadcastDep = Annotated[
    SopQualityBroadcast,
    Depends(get_sop_quality_broadcast),
]


def get_session_service(
    repository: SessionRepositoryDep,
    broadcast: SessionBroadcastDep,
) -> SessionService:
    return SessionService(repository=repository, broadcast=broadcast)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


def get_sop_quality_service(
    background_tasks: BackgroundTasks,
    request: Request,
    session: SessionDep,
    repository: SopQualityCheckRepositoryDep,
    session_repository: SessionRepositoryDep,
    session_broadcast: SessionBroadcastDep,
    broadcast: SopQualityBroadcastDep,
) -> SopQualityService:
    def schedule_check(check_id) -> None:
        executor = getattr(request.app.state, "sop_quality_check_executor", None)
        if executor is not None:
            background_tasks.add_task(executor, check_id)
            return
        background_tasks.add_task(
            run_sop_quality_check_with_new_session,
            check_id,
            broadcast=broadcast,
            session_broadcast=session_broadcast,
        )

    return SopQualityService(
        settings=settings,
        repository=repository,
        session_repository=session_repository,
        schedule_check=schedule_check,
        commit=session.commit,
        broadcast=broadcast,
    )


SopQualityServiceDep = Annotated[
    SopQualityService,
    Depends(get_sop_quality_service),
]

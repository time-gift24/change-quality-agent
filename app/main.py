from contextlib import asynccontextmanager
import logging
from time import perf_counter

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import get_mcp_runtime_manager
from app.api.v1 import agents, auth, mcp, runs, sop
from app.core.config import settings
from app.core.database import async_session
from app.core.logging import configure_logging
from app.core.security import (
    AUTH_REQUIRED_DETAIL,
    is_auth_bypass_path,
    resolve_current_user,
)
from app.repositories.runs import RunRepository
from app.repositories.users import UserRepository, seed_dev_users

configure_logging(settings)
access_logger = logging.getLogger("app.access")


async def interrupt_leftover_runs() -> None:
    async with async_session() as session:
        repository = RunRepository(session)
        await repository.interrupt_active_runs_on_startup()
        await session.commit()


async def seed_dev_users_on_startup() -> None:
    async with async_session() as session:
        repository = UserRepository(session)
        await seed_dev_users(repository)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await interrupt_leftover_runs()
    if settings.auth_dev_mode:
        await seed_dev_users_on_startup()
    mcp_runtime = get_mcp_runtime_manager()
    await mcp_runtime.start_enabled_servers()
    try:
        yield
    finally:
        await mcp_runtime.shutdown()


app = FastAPI(title="Change Quality Agent", lifespan=lifespan)


@app.middleware("http")
async def require_api_auth(request: Request, call_next):
    path = request.url.path
    if not settings.auth_enabled or is_auth_bypass_path(path):
        return await call_next(request)
    if not path.startswith("/api/"):
        return await call_next(request)

    current_user = await resolve_current_user(request)
    if current_user is None:
        response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": AUTH_REQUIRED_DETAIL},
        )
        if request.cookies.get(settings.auth_session_cookie_name) is not None:
            response.delete_cookie(settings.auth_session_cookie_name)
        return response

    request.state.current_user = current_user
    return await call_next(request)


app.include_router(auth.router)
app.include_router(mcp.router)
app.include_router(agents.router)
app.include_router(runs.router)
app.include_router(sop.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    if not settings.access_log_enabled:
        return await call_next(request)

    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        access_logger.exception(
            "%s %s failed duration_ms=%.2f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (perf_counter() - started_at) * 1000
    access_logger.info(
        "%s %s %s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

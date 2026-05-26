from contextlib import asynccontextmanager
import logging
from time import perf_counter

from fastapi import FastAPI, Request

from app.api.auth import fake_auth_middleware
from app.api.deps import get_mcp_runtime_manager
from app.api.v1 import admin_llm_providers, agents, llm_providers, mcp, runs, sop
from app.core.config import settings
from app.core.database import async_session
from app.core.logging import configure_logging
from app.repositories.runs import RunRepository

configure_logging(settings)
access_logger = logging.getLogger("app.access")


async def interrupt_leftover_runs() -> None:
    async with async_session() as session:
        repository = RunRepository(session)
        await repository.interrupt_active_runs_on_startup()
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await interrupt_leftover_runs()
    mcp_runtime = get_mcp_runtime_manager()
    await mcp_runtime.start_enabled_servers()
    try:
        yield
    finally:
        await mcp_runtime.shutdown()


app = FastAPI(title="Change Quality Agent", lifespan=lifespan)
app.middleware("http")(fake_auth_middleware)
app.include_router(mcp.router)
app.include_router(agents.router)
app.include_router(admin_llm_providers.router)
app.include_router(llm_providers.router)
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

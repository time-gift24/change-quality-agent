from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import fake_auth_middleware
from app.api.deps import get_mcp_runtime_manager
from app.api.v1 import agents, mcp, runs, sop
from app.core.database import async_session
from app.repositories.runs import RunRepository


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
app.include_router(runs.router)
app.include_router(sop.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

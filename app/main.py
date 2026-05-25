from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import mcp, runs, sop
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
    yield


app = FastAPI(title="Change Quality Agent", lifespan=lifespan)
app.include_router(mcp.router)
app.include_router(runs.router)
app.include_router(sop.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

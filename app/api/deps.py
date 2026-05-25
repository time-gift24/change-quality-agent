from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.runs import RunRepository
from app.services.sop_client import MockSopClient, SopClient

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_sop_client() -> SopClient:
    return MockSopClient()


SopClientDep = Annotated[SopClient, Depends(get_sop_client)]


def get_run_repository(session: SessionDep) -> RunRepository:
    return RunRepository(session)


RunRepositoryDep = Annotated[RunRepository, Depends(get_run_repository)]

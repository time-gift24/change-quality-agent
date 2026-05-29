from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sessions import Message, Session


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(
        self,
        title: str | None = None,
        thread_id: str | None = None,
    ) -> Session:
        runtime_session = Session(
            thread_id=thread_id or str(uuid4()),
            status="active",
            title=title,
        )
        self._session.add(runtime_session)
        await self._session.flush()
        runtime_session.latest_sequence = 0  # type: ignore[attr-defined]
        return runtime_session

    async def get_session(self, session_id: int) -> Session | None:
        runtime_session = await self._session.get(Session, session_id)
        if runtime_session is not None:
            runtime_session.latest_sequence = await self.latest_sequence(session_id)  # type: ignore[attr-defined]
        return runtime_session

    async def get_session_by_thread_id(self, thread_id: str) -> Session | None:
        statement = select(Session).where(Session.thread_id == thread_id).limit(1)
        runtime_session = await self._session.scalar(statement)
        if runtime_session is not None:
            runtime_session.latest_sequence = await self.latest_sequence(  # type: ignore[attr-defined]
                runtime_session.id
            )
        return runtime_session

    async def set_status(self, session_id: int, status: str) -> Session:
        runtime_session = await self._session.get(Session, session_id)
        if runtime_session is None:
            raise KeyError(session_id)
        runtime_session.status = status
        runtime_session.updated_at = datetime.now(UTC)
        await self._session.flush()
        runtime_session.latest_sequence = await self.latest_sequence(session_id)  # type: ignore[attr-defined]
        return runtime_session

    async def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ) -> Message:
        sequence = await self._next_sequence(session_id)
        message = Message(
            session_id=session_id,
            sequence=sequence,
            role=role,
            content=content,
            additional_kwargs=additional_kwargs or {},
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_messages_after(
        self,
        session_id: int,
        after: int = 0,
        limit: int = 100,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.sequence > after)
            .order_by(Message.sequence)
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def latest_sequence(self, session_id: int) -> int:
        statement = select(func.coalesce(func.max(Message.sequence), 0)).where(
            Message.session_id == session_id
        )
        latest = await self._session.scalar(statement)
        return int(latest or 0)

    async def commit(self) -> None:
        await self._session.commit()

    async def _next_sequence(self, session_id: int) -> int:
        await self._lock_session(session_id)
        return await self.latest_sequence(session_id) + 1

    async def _lock_session(self, session_id: int) -> None:
        statement = (
            select(Session.id).where(Session.id == session_id).with_for_update()
        )
        locked_session_id = await self._session.scalar(statement)
        if locked_session_id is None:
            raise KeyError(session_id)

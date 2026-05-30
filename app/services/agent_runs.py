"""Backend service that orchestrates a single Agent draft chat turn."""

import inspect
import logging
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from app.core.agent_runtime import AgentRuntime
from app.core.json_types import JsonObject
from app.repositories.agents import (
    AgentDisabledError,
    AgentDraftInvalidError,
    AgentNotFoundError,
    AgentRepository,
    validate_draft_config,
)
from app.services.agents import DraftAgentRuntimeConfig


logger = logging.getLogger(__name__)


class SessionRepositoryLike(Protocol):
    async def get_session(self, session_id: int): ...
    async def get_messages_after(
        self,
        session_id: int,
        after: int = 0,
        limit: int = 100,
    ): ...
    async def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        additional_kwargs=None,
    ): ...
    async def set_status(self, session_id: int, status: str): ...


class SessionBroadcastLike(Protocol):
    async def publish(self, session_id: int, message: dict) -> None: ...


class AgentRunService:
    def __init__(
        self,
        *,
        agent_repository: AgentRepository,
        session_repository: SessionRepositoryLike,
        session_broadcast: SessionBroadcastLike,
        runtime: AgentRuntime,
        commit: Callable[[], object] | None = None,
    ) -> None:
        self._agent_repository = agent_repository
        self._session_repository = session_repository
        self._session_broadcast = session_broadcast
        self._runtime = runtime
        self._commit = commit

    async def run_draft_turn(self, *, agent_id: UUID, session_id: int) -> None:
        try:
            agent = await self._agent_repository.get_agent(agent_id)
            if agent is None:
                raise AgentNotFoundError(agent_id)
            if not agent.enabled:
                raise AgentDisabledError(agent_id)
            draft = validate_draft_config(agent.draft_config, agent_id=agent_id)
            version = DraftAgentRuntimeConfig(draft)

            history = await self._load_history(session_id)
            result = await self._runtime.run(version=version, messages=history)
            await self._persist_runtime_messages(session_id, result.messages, history)
            await self._session_repository.set_status(session_id, "completed")
            await self._commit_if_configured()
            await self._publish_session_event(
                session_id,
                {"type": "completed", "session_id": session_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent draft run failed for session %s", session_id)
            try:
                await self._session_repository.set_status(session_id, "failed")
                await self._commit_if_configured()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to mark session %s as failed", session_id)
            await self._publish_session_event(
                session_id,
                {
                    "type": "failed",
                    "session_id": session_id,
                    "error": str(exc),
                },
            )

    async def _load_history(self, session_id: int) -> list[JsonObject]:
        messages = await self._session_repository.get_messages_after(
            session_id, after=0, limit=1000
        )
        history: list[JsonObject] = []
        for message in messages:
            role = getattr(message, "role", None) or message.get("role", "user")
            content = getattr(message, "content", None) or message.get("content", "")
            history.append({"role": role, "content": content})
        return history

    async def _persist_runtime_messages(
        self,
        session_id: int,
        runtime_messages: list[JsonObject],
        history: list[JsonObject],
    ) -> None:
        # Skip any echoed user messages from the runtime; only persist new
        # assistant or tool messages.
        history_len = len(history)
        new_messages = runtime_messages[history_len:] if runtime_messages else []
        if not new_messages:
            # Fallback: persist last assistant message if no slicing match.
            for message in reversed(runtime_messages):
                role = message.get("role") or message.get("type") or "assistant"
                if role in {"assistant", "ai", "tool"}:
                    new_messages = [message]
                    break

        for message in new_messages:
            role = self._normalize_role(message)
            content = self._extract_content(message)
            additional = {
                key: value
                for key, value in message.items()
                if key not in {"role", "type", "content"}
            }
            persisted = await self._session_repository.append_message(
                session_id,
                role=role,
                content=content,
                additional_kwargs=additional,
            )
            await self._publish_session_event(
                session_id,
                {
                    "type": "message",
                    "session_id": session_id,
                    "sequence": getattr(persisted, "sequence", None),
                    "role": role,
                    "content": content,
                    "additional_kwargs": additional,
                },
            )

    @staticmethod
    def _normalize_role(message: JsonObject) -> str:
        role = message.get("role") or message.get("type") or "assistant"
        if role == "ai":
            return "assistant"
        return str(role)

    @staticmethod
    def _extract_content(message: JsonObject) -> str:
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "\n".join(parts)
        return str(content)

    async def _publish_session_event(self, session_id: int, event: dict) -> None:
        try:
            await self._session_broadcast.publish(session_id, event)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish event for session %s", session_id)

    async def _commit_if_configured(self) -> None:
        if self._commit is None:
            return
        result = self._commit()
        if inspect.isawaitable(result):
            await result


__all__ = [
    "AgentRunService",
    "AgentDisabledError",
    "AgentDraftInvalidError",
    "AgentNotFoundError",
    "run_agent_draft_turn_with_new_session",
]


async def run_agent_draft_turn_with_new_session(
    agent_id: UUID,
    session_id: int,
    session_broadcast: SessionBroadcastLike | None = None,
    mcp_runtime_manager: object | None = None,
) -> None:
    """Background entrypoint used by FastAPI BackgroundTasks.

    Opens a fresh database session so the run is decoupled from the request
    that started it, then delegates to `AgentRunService`.
    """

    from app.core.agent_runtime import AgentRuntime, CapabilityToolResolver
    from app.core.database import async_session
    from app.repositories.agents import AgentRepository
    from app.repositories.llm_providers import LlmProviderRepository
    from app.repositories.mcp_servers import McpServerRepository
    from app.repositories.sessions import SessionRepository
    from app.services.agent_capabilities import AgentCapabilityService
    from app.services.agents import DatabaseLlmProviderResolver

    async with async_session() as db_session:
        agent_repository = AgentRepository(db_session)
        session_repository = SessionRepository(db_session)
        provider_repository = LlmProviderRepository(db_session)
        mcp_repository = McpServerRepository(db_session)
        capability_service = AgentCapabilityService(mcp_repository=mcp_repository)
        runtime = AgentRuntime(
            tool_resolver=CapabilityToolResolver(
                capability_service=capability_service,
                mcp_runtime=mcp_runtime_manager,
            ),
            provider_resolver=DatabaseLlmProviderResolver(provider_repository),
        )
        broadcast = session_broadcast or _NoopBroadcast()
        service = AgentRunService(
            agent_repository=agent_repository,
            session_repository=session_repository,
            session_broadcast=broadcast,
            runtime=runtime,
            commit=db_session.commit,
        )
        await service.run_draft_turn(agent_id=agent_id, session_id=session_id)


class _NoopBroadcast:
    async def publish(self, session_id: int, message: dict) -> None:
        return None

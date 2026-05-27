from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mcp import McpServer, McpServerTool


class McpServerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_server(self, **values: Any) -> McpServer:
        server = McpServer(**values)
        self._session.add(server)
        await self._session.flush()
        return server

    async def list_servers(self) -> list[McpServer]:
        statement = (
            select(McpServer)
            .options(selectinload(McpServer.tools))
            .order_by(McpServer.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_startup_servers(self) -> list[McpServer]:
        statement = (
            select(McpServer)
            .where(McpServer.enabled.is_(True))
            .where(McpServer.desired_state == "running")
            .order_by(McpServer.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_server(self, server_id: UUID) -> McpServer | None:
        statement = (
            select(McpServer)
            .options(selectinload(McpServer.tools))
            .where(McpServer.id == server_id)
        )
        return await self._session.scalar(statement)

    async def reload_server(self, server_id: UUID) -> McpServer | None:
        statement = (
            select(McpServer)
            .options(selectinload(McpServer.tools))
            .where(McpServer.id == server_id)
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(statement)

    async def require_server(self, server_id: UUID) -> McpServer:
        server = await self.get_server(server_id)
        if server is None:
            raise KeyError(server_id)
        return server

    async def update_server(self, server_id: UUID, **values: Any) -> McpServer:
        server = await self.require_server(server_id)
        for key, value in values.items():
            setattr(server, key, value)
        await self._session.flush()
        return server

    async def delete_server(self, server_id: UUID) -> None:
        server = await self.require_server(server_id)
        await self._session.delete(server)
        await self._session.flush()

    async def update_desired_state(
        self,
        server_id: UUID,
        desired_state: str,
    ) -> McpServer:
        return await self.update_server(server_id, desired_state=desired_state)

    async def update_runtime_status(
        self,
        server_id: UUID,
        *,
        runtime_status: str,
        last_error: str | None = None,
        checked: bool = False,
    ) -> McpServer:
        server = await self.require_server(server_id)
        server.runtime_status = runtime_status
        server.last_error = last_error
        if checked:
            server.last_checked_at = datetime.now(UTC)
        await self._session.flush()
        return server

    async def replace_tools(
        self,
        server_id: UUID,
        tools: list[dict[str, Any]],
    ) -> list[McpServerTool]:
        await self._session.execute(
            delete(McpServerTool).where(McpServerTool.server_id == server_id)
        )
        discovered_at = datetime.now(UTC)
        tool_models = [
            McpServerTool(
                server_id=server_id,
                name=tool["name"],
                description=tool.get("description"),
                input_schema=tool.get("input_schema") or {},
                discovered_at=discovered_at,
            )
            for tool in tools
        ]
        self._session.add_all(tool_models)
        await self._session.flush()
        return tool_models

    async def tool_count(self, server_id: UUID) -> int:
        statement = select(func.count()).select_from(McpServerTool).where(
            McpServerTool.server_id == server_id
        )
        return int((await self._session.scalar(statement)) or 0)

    async def commit(self) -> None:
        await self._session.commit()

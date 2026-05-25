from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.schemas.mcp import (
    McpDesiredState,
    McpLifecycleResponse,
    McpServerRuntimeStatus,
)


class UnsupportedMcpTransportError(Exception):
    pass


class McpCommandNotAllowedError(Exception):
    pass


@dataclass
class McpRuntimeHandle:
    exit_stack: AsyncExitStack
    session: ClientSession


class McpRepository(Protocol):
    async def require_server(self, server_id: UUID) -> Any:
        ...

    async def update_desired_state(self, server_id: UUID, desired_state: str) -> Any:
        ...

    async def update_runtime_status(
        self,
        server_id: UUID,
        *,
        runtime_status: str,
        last_error: str | None = None,
        checked: bool = False,
    ) -> Any:
        ...

    async def replace_tools(
        self,
        server_id: UUID,
        tools: list[dict[str, Any]],
    ) -> Any:
        ...

    async def tool_count(self, server_id: UUID) -> int:
        ...

    async def commit(self) -> None:
        ...


class McpProbe(Protocol):
    async def start(self, server: Any) -> tuple[Any, list[dict[str, Any]]]:
        ...

    async def list_tools(self, handle: Any) -> list[dict[str, Any]]:
        ...

    async def stop(self, handle: Any) -> None:
        ...


class StdioMcpProbe:
    def __init__(self, allowed_commands: set[str] | None = None) -> None:
        self._allowed_commands = allowed_commands or {
            "uvx",
            "npx",
            "node",
            "python",
        }

    async def start(
        self,
        server: Any,
    ) -> tuple[McpRuntimeHandle, list[dict[str, Any]]]:
        if server.command not in self._allowed_commands:
            raise McpCommandNotAllowedError(server.command or "")

        exit_stack = AsyncExitStack()
        try:
            params = StdioServerParameters(
                command=server.command,
                args=server.args,
                env=server.env,
            )
            read_stream, write_stream = await exit_stack.enter_async_context(
                stdio_client(params)
            )
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            handle = McpRuntimeHandle(exit_stack=exit_stack, session=session)
            return handle, await self.list_tools(handle)
        except Exception:
            await exit_stack.aclose()
            raise

    async def list_tools(self, handle: McpRuntimeHandle) -> list[dict[str, Any]]:
        tools_result = await handle.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema or {},
            }
            for tool in tools_result.tools
        ]

    async def stop(self, handle: McpRuntimeHandle) -> None:
        await handle.exit_stack.aclose()


class McpRuntimeManager:
    def __init__(
        self,
        *,
        repository_factory: Callable[[], McpRepository],
        probe: McpProbe | None = None,
    ) -> None:
        self._repository_factory = repository_factory
        self._probe = probe or StdioMcpProbe()
        self._handles: dict[UUID, Any] = {}

    async def start(self, server_id: UUID) -> McpLifecycleResponse:
        repository = self._repository_factory()
        server = await repository.require_server(server_id)
        self._require_supported_transport(server)
        await repository.update_desired_state(
            server_id,
            McpDesiredState.running.value,
        )

        if server_id in self._handles:
            await repository.commit()
            return await self._response(repository, server_id)

        await repository.update_runtime_status(
            server_id,
            runtime_status=McpServerRuntimeStatus.starting.value,
        )
        handle = None
        try:
            handle, tools = await self._probe.start(server)
            await repository.replace_tools(server_id, tools)
            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.running.value,
                last_error=None,
                checked=True,
            )
        except Exception as exc:
            if handle is not None:
                await self._probe.stop(handle)
            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.error.value,
                last_error=str(exc),
                checked=True,
            )
            await repository.commit()
            raise

        self._handles[server_id] = handle
        await repository.commit()
        return await self._response(repository, server_id)

    async def stop(self, server_id: UUID) -> McpLifecycleResponse:
        repository = self._repository_factory()
        await repository.update_desired_state(
            server_id,
            McpDesiredState.stopped.value,
        )
        await repository.update_runtime_status(
            server_id,
            runtime_status=McpServerRuntimeStatus.stopping.value,
        )
        handle = self._handles.pop(server_id, None)
        if handle is not None:
            await self._probe.stop(handle)
        await repository.update_runtime_status(
            server_id,
            runtime_status=McpServerRuntimeStatus.stopped.value,
            last_error=None,
        )
        await repository.commit()
        return await self._response(repository, server_id)

    async def restart(self, server_id: UUID) -> McpLifecycleResponse:
        await self.stop(server_id)
        return await self.start(server_id)

    async def check(self, server_id: UUID) -> McpLifecycleResponse:
        repository = self._repository_factory()
        server = await repository.require_server(server_id)
        self._require_supported_transport(server)

        handle = self._handles.get(server_id)
        temporary_handle = None
        try:
            if handle is None:
                temporary_handle, tools = await self._probe.start(server)
            else:
                tools = await self._probe.list_tools(handle)

            await repository.replace_tools(server_id, tools)
            await repository.update_runtime_status(
                server_id,
                runtime_status=server.runtime_status,
                last_error=None,
                checked=True,
            )
            await repository.commit()
        except Exception as exc:
            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.error.value,
                last_error=str(exc),
                checked=True,
            )
            await repository.commit()
            raise
        finally:
            if temporary_handle is not None:
                await self._probe.stop(temporary_handle)
        return await self._response(repository, server_id)

    async def shutdown(self) -> None:
        for server_id, handle in list(self._handles.items()):
            repository = self._repository_factory()
            self._handles.pop(server_id, None)
            try:
                await self._probe.stop(handle)
            except Exception as exc:
                await repository.update_runtime_status(
                    server_id,
                    runtime_status=McpServerRuntimeStatus.error.value,
                    last_error=str(exc),
                    checked=True,
                )
                await repository.commit()
                continue

            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.stopped.value,
                last_error=None,
            )
            await repository.commit()

    async def _response(
        self,
        repository: McpRepository,
        server_id: UUID,
    ) -> McpLifecycleResponse:
        server = await repository.require_server(server_id)
        return McpLifecycleResponse(
            server_id=server.id,
            desired_state=server.desired_state,
            runtime_status=server.runtime_status,
            last_checked_at=server.last_checked_at,
            last_error=server.last_error,
            tool_count=await repository.tool_count(server_id),
        )

    def _require_supported_transport(self, server: Any) -> None:
        if server.transport != "stdio":
            raise UnsupportedMcpTransportError(server.transport)

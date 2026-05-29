from collections.abc import Awaitable, Callable
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.repositories.mcp_servers import McpServerRepository
from app.schemas.mcp import (
    McpLifecycleResponse,
    McpServerCreate,
    McpServerUpdate,
)
from app.services.mcp_runtime import McpRuntimeManager


class McpServerNotFoundError(KeyError):
    pass


class McpServerNameConflictError(ValueError):
    pass


class McpServerUpdateConflictError(RuntimeError):
    pass


class McpServerValidationError(ValueError):
    def __init__(self, errors: list[dict[str, object]]) -> None:
        self.errors = errors
        super().__init__("MCP server validation failed.")


class McpServerService:
    def __init__(
        self,
        *,
        repository: McpServerRepository,
        runtime: McpRuntimeManager,
    ) -> None:
        self._repository = repository
        self._runtime = runtime

    async def list_servers(self) -> object:
        return await self._repository.list_servers()

    async def create_server(self, payload: McpServerCreate) -> object:
        try:
            server = await self._repository.create_server(
                **payload.model_dump(mode="json")
            )
            await self._repository.commit()
        except IntegrityError as exc:
            raise McpServerNameConflictError() from exc

        if _should_start_after_save(server):
            await _run_lifecycle(self._runtime.start, server.id)
            reloaded = await self._repository.reload_server(server.id)
            if reloaded is not None:
                server = reloaded

        return server

    async def get_server(self, server_id: UUID) -> object:
        server = await self._repository.get_server(server_id)
        if server is None:
            raise McpServerNotFoundError(server_id)
        return server

    async def update_server(self, server_id: UUID, payload: McpServerUpdate) -> object:
        async with self._runtime.server_operation_lock(server_id):
            server = await self._repository.get_server(server_id)
            if server is None:
                raise McpServerNotFoundError(server_id)
            if server.runtime_status == "running" or self._runtime.is_running(
                server_id
            ):
                raise McpServerUpdateConflictError()

            values = _validated_update_values(
                server,
                payload.model_dump(exclude_unset=True, mode="json"),
            )
            try:
                server = await self._repository.update_server(server_id, **values)
                await self._repository.commit()
            except IntegrityError as exc:
                raise McpServerNameConflictError() from exc

            if _should_start_after_save(server):
                await _run_lifecycle(self._runtime.start, server_id)
                reloaded = await self._repository.reload_server(server_id)
                if reloaded is not None:
                    server = reloaded

            return server

    async def delete_server(self, server_id: UUID) -> None:
        async with self._runtime.server_operation_lock(server_id):
            server = await self._repository.get_server(server_id)
            if server is None:
                raise McpServerNotFoundError(server_id)
            if server.runtime_status == "running" or self._runtime.is_running(
                server_id
            ):
                await _run_lifecycle(self._runtime.stop_locked, server_id)

            await self._repository.delete_server(server_id)
            await self._repository.commit()

    async def start_server(self, server_id: UUID) -> McpLifecycleResponse:
        return await _run_lifecycle(self._runtime.start, server_id)

    async def stop_server(self, server_id: UUID) -> McpLifecycleResponse:
        return await _run_lifecycle(self._runtime.stop, server_id)

    async def restart_server(self, server_id: UUID) -> McpLifecycleResponse:
        return await _run_lifecycle(self._runtime.restart, server_id)

    async def check_server(self, server_id: UUID) -> McpLifecycleResponse:
        return await _run_lifecycle(self._runtime.check, server_id)


def _validated_update_values(
    server: object, values: dict[str, object]
) -> dict[str, object]:
    merged = {
        "name": server.name,
        "transport": server.transport,
        "command": server.command,
        "args": server.args,
        "env": server.env,
        "url": server.url,
        "headers": server.headers,
        "enabled": server.enabled,
        "desired_state": server.desired_state,
    }
    merged.update(values)
    try:
        validated = McpServerCreate(**merged).model_dump(mode="json")
    except ValidationError as exc:
        raise McpServerValidationError(exc.errors(include_context=False)) from exc
    return {key: validated[key] for key in values}


def _should_start_after_save(server: object) -> bool:
    return bool(server.enabled) and server.desired_state == "running"


async def _run_lifecycle(
    operation: Callable[[UUID], Awaitable[McpLifecycleResponse]],
    server_id: UUID,
) -> McpLifecycleResponse:
    try:
        return await operation(server_id)
    except KeyError as exc:
        raise McpServerNotFoundError(server_id) from exc

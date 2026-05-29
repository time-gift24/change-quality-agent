import asyncio
import logging
import re
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from app.schemas.mcp import (
    McpDesiredState,
    McpLifecycleResponse,
    McpServerRuntimeStatus,
)

logger = logging.getLogger(__name__)


class UnsupportedMcpTransportError(Exception):
    pass


class McpCommandNotAllowedError(Exception):
    pass


class McpRuntimeNotEnabledError(Exception):
    pass


MCP_OPERATION_TIMEOUT_MESSAGE = "MCP operation timed out."
MCP_RUNTIME_NOT_ENABLED_MESSAGE = (
    "MCP runtime requires mcp_runtime_single_instance=true."
)
REDACTED_ERROR_VALUE = "[redacted]"
_SENSITIVE_ERROR_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|secret|password|api[_-]?key|authorization|credential)"
    r"(\s*[:=]\s*)(['\"]?)(bearer\s+)?([^\s,;'\"}]+)(['\"]?)"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)(bearer\s+)([^\s,;'\"}]+)")


@dataclass
class McpRuntimeHandle:
    exit_stack: AsyncExitStack
    session: ClientSession


@dataclass
class TransportMcpRuntimeHandle:
    transport: str
    handle: Any


@dataclass
class TaskOwnedMcpRuntimeHandle:
    task: asyncio.Task[None]
    commands: asyncio.Queue[Any]


@dataclass
class _TaskOwnedMcpCommand:
    name: str
    future: asyncio.Future[Any]


class McpRepository(Protocol):
    async def require_server(self, server_id: UUID) -> Any: ...

    async def list_startup_servers(self) -> list[Any]: ...

    async def update_desired_state(
        self, server_id: UUID, desired_state: str
    ) -> Any: ...

    async def update_runtime_status(
        self,
        server_id: UUID,
        *,
        runtime_status: str,
        last_error: str | None = None,
        checked: bool = False,
    ) -> Any: ...

    async def replace_tools(
        self,
        server_id: UUID,
        tools: list[dict[str, Any]],
    ) -> Any: ...

    async def tool_count(self, server_id: UUID) -> int: ...

    async def commit(self) -> None: ...


class McpProbe(Protocol):
    async def start(self, server: Any) -> tuple[Any, list[dict[str, Any]]]: ...

    async def list_tools(self, handle: Any) -> list[dict[str, Any]]: ...

    async def stop(self, handle: Any) -> None: ...


class StdioMcpProbe:
    def __init__(
        self,
        allowed_commands: set[str] | None = None,
        allowed_stdio_specs: set[str] | None = None,
    ) -> None:
        self._allowed_commands = set(allowed_commands or ())
        self._allowed_stdio_specs = set(allowed_stdio_specs or ())

    async def start(
        self,
        server: Any,
    ) -> tuple[McpRuntimeHandle, list[dict[str, Any]]]:
        if server.command not in self._allowed_commands:
            raise McpCommandNotAllowedError(server.command or "")
        stdio_spec = self._stdio_spec(server)
        if not self._allowed_stdio_specs or stdio_spec not in self._allowed_stdio_specs:
            raise McpCommandNotAllowedError(stdio_spec)

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
            return handle, await _list_session_tools(handle)
        except BaseException:
            await _close_failed_startup_stack(exit_stack)
            raise

    async def list_tools(self, handle: McpRuntimeHandle) -> list[dict[str, Any]]:
        return await _list_session_tools(handle)

    async def stop(self, handle: McpRuntimeHandle) -> None:
        await handle.exit_stack.aclose()

    def _stdio_spec(self, server: Any) -> str:
        first_arg = server.args[0] if server.args else ""
        return f"{server.command}:{first_arg}"


class StreamableHttpMcpProbe:
    async def start(
        self,
        server: Any,
    ) -> tuple[McpRuntimeHandle, list[dict[str, Any]]]:
        exit_stack = AsyncExitStack()
        try:
            read_stream, write_stream, _get_session_id = (
                await exit_stack.enter_async_context(
                    streamablehttp_client(server.url, headers=server.headers or {})
                )
            )
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            handle = McpRuntimeHandle(exit_stack=exit_stack, session=session)
            return handle, await _list_session_tools(handle)
        except BaseException:
            await _close_failed_startup_stack(exit_stack)
            raise

    async def list_tools(self, handle: McpRuntimeHandle) -> list[dict[str, Any]]:
        return await _list_session_tools(handle)

    async def stop(self, handle: McpRuntimeHandle) -> None:
        await handle.exit_stack.aclose()


class TransportMcpProbe:
    def __init__(
        self,
        *,
        stdio_probe: McpProbe | None = None,
        http_probe: McpProbe | None = None,
    ) -> None:
        self._stdio_probe = stdio_probe or StdioMcpProbe()
        self._http_probe = http_probe or StreamableHttpMcpProbe()

    async def start(
        self,
        server: Any,
    ) -> tuple[TransportMcpRuntimeHandle, list[dict[str, Any]]]:
        probe = self._probe_for_transport(server.transport)
        handle, tools = await probe.start(server)
        return (
            TransportMcpRuntimeHandle(transport=server.transport, handle=handle),
            tools,
        )

    async def list_tools(
        self, handle: TransportMcpRuntimeHandle
    ) -> list[dict[str, Any]]:
        return await self._probe_for_transport(handle.transport).list_tools(
            handle.handle
        )

    async def stop(self, handle: TransportMcpRuntimeHandle) -> None:
        await self._probe_for_transport(handle.transport).stop(handle.handle)

    def _probe_for_transport(self, transport: str) -> McpProbe:
        if transport == "stdio":
            return self._stdio_probe
        if transport == "http":
            return self._http_probe
        raise UnsupportedMcpTransportError(transport)


class TaskOwnedMcpProbe:
    def __init__(self, probe: McpProbe) -> None:
        self.inner_probe = probe

    async def start(
        self,
        server: Any,
    ) -> tuple[TaskOwnedMcpRuntimeHandle, list[dict[str, Any]]]:
        loop = asyncio.get_running_loop()
        started: asyncio.Future[list[dict[str, Any]]] = loop.create_future()
        commands: asyncio.Queue[Any] = asyncio.Queue()
        task = asyncio.create_task(self._run(server, started, commands))
        handle = TaskOwnedMcpRuntimeHandle(task=task, commands=commands)

        try:
            tools = await started
        except BaseException:
            task.cancel()
            with suppress(BaseException):
                await task
            raise
        return handle, tools

    async def list_tools(
        self,
        handle: TaskOwnedMcpRuntimeHandle,
    ) -> list[dict[str, Any]]:
        return await self._send(handle, "list_tools")

    async def stop(self, handle: TaskOwnedMcpRuntimeHandle) -> None:
        try:
            await self._send(handle, "stop")
        finally:
            if handle.task.done():
                with suppress(BaseException):
                    await handle.task

    async def _run(
        self,
        server: Any,
        started: asyncio.Future[list[dict[str, Any]]],
        commands: asyncio.Queue[Any],
    ) -> None:
        inner_handle = None
        try:
            inner_handle, tools = await self.inner_probe.start(server)
            _set_future_result(started, tools)

            while True:
                command = await commands.get()
                if command.name == "list_tools":
                    try:
                        tools = await self.inner_probe.list_tools(inner_handle)
                    except Exception as exc:
                        _set_future_exception(command.future, exc)
                    except BaseException as exc:
                        _set_future_exception(command.future, exc)
                        raise
                    else:
                        _set_future_result(command.future, tools)
                    continue

                if command.name == "stop":
                    try:
                        await self.inner_probe.stop(inner_handle)
                    except Exception as exc:
                        _set_future_exception(command.future, exc)
                    except BaseException as exc:
                        _set_future_exception(command.future, exc)
                        raise
                    else:
                        _set_future_result(command.future, None)
                        return
        except BaseException as exc:
            _set_future_exception(started, exc)
            raise

    async def _send(self, handle: TaskOwnedMcpRuntimeHandle, name: str) -> Any:
        if handle.task.done():
            await handle.task
            raise RuntimeError("MCP runtime worker is not running.")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        await handle.commands.put(_TaskOwnedMcpCommand(name=name, future=future))
        return await future


async def _list_session_tools(handle: McpRuntimeHandle) -> list[dict[str, Any]]:
    tools_result = await handle.session.list_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema or {},
        }
        for tool in tools_result.tools
    ]


async def _close_failed_startup_stack(exit_stack: AsyncExitStack) -> None:
    try:
        await exit_stack.aclose()
    except BaseException:
        logger.debug(
            "Failed to close MCP startup resources after start failure.",
            exc_info=True,
        )


class McpRuntimeManager:
    def __init__(
        self,
        *,
        repository_factory: Callable[[], Any],
        probe: McpProbe | None = None,
        operation_timeout_seconds: float | None = 10.0,
        single_instance_confirmed: bool = True,
    ) -> None:
        self._repository_factory = repository_factory
        self._probe = _task_owned_probe(probe or TransportMcpProbe())
        self._operation_timeout_seconds = operation_timeout_seconds
        self._single_instance_confirmed = single_instance_confirmed
        self._handles: dict[UUID, Any] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}

    async def start(self, server_id: UUID) -> McpLifecycleResponse:
        self._require_runtime_enabled()
        async with self._lock_for(server_id):
            return await self._start_locked(server_id)

    async def _start_locked(self, server_id: UUID) -> McpLifecycleResponse:
        async with self._repository_context() as repository:
            server = await repository.require_server(server_id)
            self._require_supported_transport(server)
            await repository.update_desired_state(
                server_id,
                McpDesiredState.running.value,
            )

            if server_id in self._handles:
                await repository.update_runtime_status(
                    server_id,
                    runtime_status=McpServerRuntimeStatus.running.value,
                    last_error=None,
                    checked=True,
                )
                await repository.commit()
                return await self._response(repository, server_id)

            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.starting.value,
            )
            handle = None
            try:
                handle, tools = await self._run_operation(self._probe.start(server))
                await repository.replace_tools(server_id, tools)
                await repository.update_runtime_status(
                    server_id,
                    runtime_status=McpServerRuntimeStatus.running.value,
                    last_error=None,
                    checked=True,
                )
            except Exception as exc:
                if handle is not None:
                    await self._run_operation(self._probe.stop(handle))
                await repository.update_runtime_status(
                    server_id,
                    runtime_status=McpServerRuntimeStatus.error.value,
                    last_error=sanitize_mcp_error(exc, server),
                    checked=True,
                )
                await repository.commit()
                raise

            self._handles[server_id] = handle
            await repository.commit()
            return await self._response(repository, server_id)

    async def stop(self, server_id: UUID) -> McpLifecycleResponse:
        async with self._lock_for(server_id):
            return await self._stop_locked(server_id)

    @asynccontextmanager
    async def server_operation_lock(self, server_id: UUID) -> AsyncIterator[None]:
        async with self._lock_for(server_id):
            yield

    async def stop_locked(self, server_id: UUID) -> McpLifecycleResponse:
        return await self._stop_locked(server_id)

    async def _stop_locked(self, server_id: UUID) -> McpLifecycleResponse:
        async with self._repository_context() as repository:
            server = await repository.require_server(server_id)
            await repository.update_desired_state(
                server_id,
                McpDesiredState.stopped.value,
            )
            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.stopping.value,
            )
            handle = self._handles.get(server_id)
            if handle is not None:
                try:
                    await self._run_operation(self._probe.stop(handle))
                except Exception as exc:
                    await repository.update_runtime_status(
                        server_id,
                        runtime_status=McpServerRuntimeStatus.error.value,
                        last_error=sanitize_mcp_error(exc, server),
                        checked=True,
                    )
                    await repository.commit()
                    raise
                self._handles.pop(server_id, None)
            await repository.update_runtime_status(
                server_id,
                runtime_status=McpServerRuntimeStatus.stopped.value,
                last_error=None,
            )
            await repository.commit()
            return await self._response(repository, server_id)

    async def restart(self, server_id: UUID) -> McpLifecycleResponse:
        self._require_runtime_enabled()
        async with self._lock_for(server_id):
            await self._stop_locked(server_id)
            return await self._start_locked(server_id)

    async def start_enabled_servers(self) -> None:
        async with self._repository_context() as repository:
            servers = await repository.list_startup_servers()

        if not self._single_instance_confirmed:
            for server in servers:
                async with self._repository_context() as repository:
                    await repository.update_runtime_status(
                        server.id,
                        runtime_status=McpServerRuntimeStatus.error.value,
                        last_error=MCP_RUNTIME_NOT_ENABLED_MESSAGE,
                        checked=True,
                    )
                    await repository.commit()
            return

        for server in servers:
            try:
                await self.start(server.id)
            except Exception as exc:
                logger.warning(
                    "Failed to start MCP server during startup.",
                    extra={"server_id": str(server.id), "server_name": server.name},
                    exc_info=True,
                )
                async with self._repository_context() as repository:
                    current = await repository.require_server(server.id)
                    if (
                        current.runtime_status != McpServerRuntimeStatus.error.value
                        or not current.last_error
                    ):
                        await repository.update_runtime_status(
                            server.id,
                            runtime_status=McpServerRuntimeStatus.error.value,
                            last_error=sanitize_mcp_error(exc, server),
                            checked=True,
                        )
                        await repository.commit()

    async def check(self, server_id: UUID) -> McpLifecycleResponse:
        self._require_runtime_enabled()
        async with self._lock_for(server_id):
            return await self._check_locked(server_id)

    async def _check_locked(self, server_id: UUID) -> McpLifecycleResponse:
        async with self._repository_context() as repository:
            server = await repository.require_server(server_id)
            self._require_supported_transport(server)

            handle = self._handles.get(server_id)
            temporary_handle = None
            try:
                if handle is None:
                    temporary_handle, tools = await self._run_operation(
                        self._probe.start(server)
                    )
                else:
                    tools = await self._run_operation(self._probe.list_tools(handle))

                await repository.replace_tools(server_id, tools)
                runtime_status = (
                    McpServerRuntimeStatus.running.value
                    if handle is not None
                    else McpServerRuntimeStatus.stopped.value
                )
                await repository.update_runtime_status(
                    server_id,
                    runtime_status=runtime_status,
                    last_error=None,
                    checked=True,
                )
                await repository.commit()
            except Exception as exc:
                await repository.update_runtime_status(
                    server_id,
                    runtime_status=McpServerRuntimeStatus.error.value,
                    last_error=sanitize_mcp_error(exc, server),
                    checked=True,
                )
                await repository.commit()
                raise
            finally:
                if temporary_handle is not None:
                    await self._run_operation(self._probe.stop(temporary_handle))
            return await self._response(repository, server_id)

    async def shutdown(self) -> None:
        for server_id, handle in list(self._handles.items()):
            async with self._repository_context() as repository:
                server = await repository.require_server(server_id)
                try:
                    await self._run_operation(self._probe.stop(handle))
                except Exception as exc:
                    await repository.update_runtime_status(
                        server_id,
                        runtime_status=McpServerRuntimeStatus.error.value,
                        last_error=sanitize_mcp_error(exc, server),
                        checked=True,
                    )
                    await repository.commit()
                    continue

                self._handles.pop(server_id, None)
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
        if server.transport not in {"stdio", "http"}:
            raise UnsupportedMcpTransportError(server.transport)

    def _require_runtime_enabled(self) -> None:
        if not self._single_instance_confirmed:
            raise McpRuntimeNotEnabledError(MCP_RUNTIME_NOT_ENABLED_MESSAGE)

    def is_running(self, server_id: UUID) -> bool:
        return server_id in self._handles

    def _lock_for(self, server_id: UUID) -> asyncio.Lock:
        lock = self._locks.get(server_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[server_id] = lock
        return lock

    async def _run_operation(self, operation: object) -> object:
        if self._operation_timeout_seconds is None:
            return await operation
        try:
            return await asyncio.wait_for(
                operation,
                timeout=self._operation_timeout_seconds,
            )
        except TimeoutError as exc:
            raise TimeoutError(MCP_OPERATION_TIMEOUT_MESSAGE) from exc

    @asynccontextmanager
    async def _repository_context(self) -> AsyncIterator[McpRepository]:
        repository_or_context = self._repository_factory()
        if hasattr(repository_or_context, "__aenter__"):
            async with repository_or_context as repository:
                yield repository
            return

        yield repository_or_context


def _task_owned_probe(probe: McpProbe) -> TaskOwnedMcpProbe:
    if isinstance(probe, TaskOwnedMcpProbe):
        return probe
    return TaskOwnedMcpProbe(probe)


def _set_future_result(future: asyncio.Future[Any], result: Any) -> None:
    if not future.done():
        future.set_result(result)


def _set_future_exception(future: asyncio.Future[Any], exc: BaseException) -> None:
    if not future.done():
        future.set_exception(exc)


def sanitize_mcp_error(exc: Exception, server: Any | None = None) -> str:
    message = str(exc) or MCP_OPERATION_TIMEOUT_MESSAGE
    for secret in sorted(_server_secret_values(server), key=len, reverse=True):
        message = message.replace(secret, REDACTED_ERROR_VALUE)
    message = _BEARER_TOKEN_RE.sub(r"\1" + REDACTED_ERROR_VALUE, message)
    return _SENSITIVE_ERROR_ASSIGNMENT_RE.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}{match.group(3)}"
            f"{match.group(4) or ''}{REDACTED_ERROR_VALUE}{match.group(6)}"
        ),
        message,
    )


def _server_secret_values(server: Any | None) -> set[str]:
    if server is None:
        return set()

    secrets: set[str] = set()
    for mapping_name in ("env", "headers"):
        mapping = getattr(server, mapping_name, None)
        if not isinstance(mapping, dict):
            continue
        for value in mapping.values():
            if isinstance(value, str) and value:
                secrets.add(value)
    return secrets

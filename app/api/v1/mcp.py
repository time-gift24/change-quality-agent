from typing import Annotated, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    McpRepositoryDep,
    McpRuntimeManagerDep,
    require_mcp_admin,
)
from app.schemas.mcp import (
    McpLifecycleResponse,
    McpServerCreate,
    McpServerDetail,
    McpServerSummary,
    McpServerUpdate,
)
from app.services.mcp_runtime import (
    McpCommandNotAllowedError,
    UnsupportedMcpTransportError,
)

router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp"],
    dependencies=[Depends(require_mcp_admin)],
)


@router.get("/servers")
async def list_mcp_servers(repository: McpRepositoryDep) -> list[McpServerSummary]:
    servers = await repository.list_servers()
    return [_server_summary(server) for server in servers]


@router.post(
    "/servers",
    response_model=McpServerDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_server(
    payload: McpServerCreate,
    repository: McpRepositoryDep,
) -> McpServerDetail:
    try:
        server = await repository.create_server(**payload.model_dump(mode="json"))
        await repository.commit()
    except IntegrityError as exc:
        raise _name_conflict() from exc
    return _server_detail(server)


@router.get("/servers/{server_id}")
async def get_mcp_server(
    server_id: Annotated[UUID, Path()],
    repository: McpRepositoryDep,
) -> McpServerDetail:
    server = await repository.get_server(server_id)
    if server is None:
        raise _not_found()
    return _server_detail(server)


@router.patch("/servers/{server_id}")
async def update_mcp_server(
    server_id: Annotated[UUID, Path()],
    payload: McpServerUpdate,
    repository: McpRepositoryDep,
    runtime: McpRuntimeManagerDep,
) -> McpServerDetail:
    server = await repository.get_server(server_id)
    if server is None:
        raise _not_found()
    if server.runtime_status == "running" or runtime.is_running(server_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop the MCP server before updating its configuration.",
        )

    values = _validated_update_values(
        server,
        payload.model_dump(exclude_unset=True, mode="json"),
    )
    try:
        server = await repository.update_server(server_id, **values)
        await repository.commit()
    except IntegrityError as exc:
        raise _name_conflict() from exc
    return _server_detail(server)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    server_id: Annotated[UUID, Path()],
    repository: McpRepositoryDep,
    runtime: McpRuntimeManagerDep,
) -> None:
    server = await repository.get_server(server_id)
    if server is None:
        raise _not_found()
    if server.runtime_status == "running" or runtime.is_running(server_id):
        await _run_lifecycle(runtime.stop, server_id)

    await repository.delete_server(server_id)
    await repository.commit()


@router.post("/servers/{server_id}/start")
async def start_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.start, server_id)


@router.post("/servers/{server_id}/stop")
async def stop_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.stop, server_id)


@router.post("/servers/{server_id}/restart")
async def restart_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.restart, server_id)


@router.post("/servers/{server_id}/check")
async def check_mcp_server(
    server_id: Annotated[UUID, Path()],
    runtime: McpRuntimeManagerDep,
) -> McpLifecycleResponse:
    return await _run_lifecycle(runtime.check, server_id)


def _server_summary(server) -> McpServerSummary:
    return McpServerSummary.model_validate(server).model_copy(
        update={"tool_count": len(getattr(server, "tools", []) or [])}
    )


def _server_detail(server) -> McpServerDetail:
    return McpServerDetail.model_validate(server)


def _validated_update_values(server, values: dict[str, object]) -> dict[str, object]:
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(include_context=False),
        ) from exc
    return {key: validated[key] for key in values}


async def _run_lifecycle(
    operation: Callable[[UUID], Awaitable[McpLifecycleResponse]],
    server_id: UUID,
) -> McpLifecycleResponse:
    try:
        return await operation(server_id)
    except KeyError as exc:
        raise _not_found() from exc
    except UnsupportedMcpTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported MCP transport: {exc}",
        ) from exc
    except McpCommandNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP stdio command is not allowed.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="MCP lifecycle operation failed.",
        ) from exc


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="MCP server not found.",
    )


def _name_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="MCP server name already exists.",
    )

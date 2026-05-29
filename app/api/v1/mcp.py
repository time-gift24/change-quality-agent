from typing import Annotated, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import (
    McpServerServiceDep,
    require_admin_user,
)
from app.schemas.mcp import (
    McpLifecycleResponse,
    McpServerCreate,
    McpServerDetail,
    McpServerSummary,
    McpServerUpdate,
)
from app.services.mcp_servers import (
    McpServerNameConflictError,
    McpServerNotFoundError,
    McpServerUpdateConflictError,
    McpServerValidationError,
)
from app.services.mcp_runtime import (
    McpCommandNotAllowedError,
    McpRuntimeNotEnabledError,
    UnsupportedMcpTransportError,
    sanitize_mcp_error,
)

router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp"],
    dependencies=[Depends(require_admin_user)],
)


@router.get("/servers")
async def list_mcp_servers(service: McpServerServiceDep) -> list[McpServerSummary]:
    servers = await service.list_servers()
    return [_server_summary(server) for server in servers]


@router.post(
    "/servers",
    response_model=McpServerDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_server(
    payload: McpServerCreate,
    service: McpServerServiceDep,
) -> McpServerDetail:
    server = await _run_service(lambda: service.create_server(payload))
    return _server_detail(server)


@router.get("/servers/{server_id}")
async def get_mcp_server(
    server_id: Annotated[UUID, Path()],
    service: McpServerServiceDep,
) -> McpServerDetail:
    server = await _run_service(lambda: service.get_server(server_id))
    return _server_detail(server)


@router.patch("/servers/{server_id}")
async def update_mcp_server(
    server_id: Annotated[UUID, Path()],
    payload: McpServerUpdate,
    service: McpServerServiceDep,
) -> McpServerDetail:
    server = await _run_service(lambda: service.update_server(server_id, payload))
    return _server_detail(server)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    server_id: Annotated[UUID, Path()],
    service: McpServerServiceDep,
) -> None:
    await _run_service(lambda: service.delete_server(server_id))


@router.post("/servers/{server_id}/start")
async def start_mcp_server(
    server_id: Annotated[UUID, Path()],
    service: McpServerServiceDep,
) -> McpLifecycleResponse:
    return await _run_service(lambda: service.start_server(server_id))


@router.post("/servers/{server_id}/stop")
async def stop_mcp_server(
    server_id: Annotated[UUID, Path()],
    service: McpServerServiceDep,
) -> McpLifecycleResponse:
    return await _run_service(lambda: service.stop_server(server_id))


@router.post("/servers/{server_id}/restart")
async def restart_mcp_server(
    server_id: Annotated[UUID, Path()],
    service: McpServerServiceDep,
) -> McpLifecycleResponse:
    return await _run_service(lambda: service.restart_server(server_id))


@router.post("/servers/{server_id}/check")
async def check_mcp_server(
    server_id: Annotated[UUID, Path()],
    service: McpServerServiceDep,
) -> McpLifecycleResponse:
    return await _run_service(lambda: service.check_server(server_id))


def _server_summary(server) -> McpServerSummary:
    return McpServerSummary.model_validate(server).model_copy(
        update={"tool_count": len(getattr(server, "tools", []) or [])}
    )


def _server_detail(server) -> McpServerDetail:
    return McpServerDetail.model_validate(server)


async def _run_service(operation: Callable[[], Awaitable[object]]):
    try:
        return await operation()
    except McpServerNotFoundError as exc:
        raise _not_found() from exc
    except McpServerNameConflictError as exc:
        raise _name_conflict() from exc
    except McpServerUpdateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop the MCP server before updating its configuration.",
        ) from exc
    except McpServerValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors,
        ) from exc
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
    except McpRuntimeNotEnabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        sanitized_error = sanitize_mcp_error(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP lifecycle operation failed: {sanitized_error}",
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

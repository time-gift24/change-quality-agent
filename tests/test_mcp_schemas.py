from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.mcp import McpServer, McpServerTool as McpServerToolModel
from app.schemas.mcp import (
    McpServerCreate,
    McpServerDetail,
    McpServerRuntimeStatus,
    McpServerTool,
    McpTransport,
)


def test_mcp_server_response_redacts_env_and_headers() -> None:
    server = McpServerDetail(
        id=uuid4(),
        name="filesystem",
        transport=McpTransport.stdio,
        command="uvx",
        args=["mcp-server-filesystem"],
        env={"TOKEN": "secret"},
        url=None,
        headers={"Authorization": "Bearer secret"},
        enabled=True,
        desired_state="running",
        runtime_status=McpServerRuntimeStatus.running,
        last_checked_at=datetime.now(UTC),
        last_error=None,
        tool_count=0,
        tools=[],
    )

    body = server.model_dump(mode="json")

    assert body["env"] == {"TOKEN": "********"}
    assert body["headers"] == {"Authorization": "********"}


def test_mcp_tool_schema_defaults_input_schema() -> None:
    tool = McpServerTool(name="search", description=None)

    assert tool.input_schema == {}


def test_mcp_server_detail_validates_nested_orm_like_tools() -> None:
    server = SimpleNamespace(
        id=uuid4(),
        name="filesystem",
        transport="stdio",
        command="uvx",
        args=["mcp-server-filesystem"],
        env={},
        url=None,
        headers={},
        enabled=True,
        desired_state="running",
        runtime_status="running",
        last_checked_at=None,
        last_error=None,
        tool_count=1,
        tools=[
            SimpleNamespace(
                name="search",
                description="Search files",
                input_schema={"type": "object"},
                discovered_at=datetime.now(UTC),
            ),
        ],
    )

    detail = McpServerDetail.model_validate(server)

    assert detail.tools[0].name == "search"
    assert detail.tools[0].input_schema == {"type": "object"}


def test_mcp_server_create_rejects_blank_stdio_command() -> None:
    with pytest.raises(ValidationError, match="stdio MCP servers require command"):
        McpServerCreate(
            name="filesystem",
            transport=McpTransport.stdio,
            command="   ",
        )


def test_mcp_server_create_rejects_invalid_http_url() -> None:
    with pytest.raises(ValidationError, match="http MCP servers require valid url"):
        McpServerCreate(
            name="remote",
            transport=McpTransport.http,
            url="not-a-url",
        )


def test_mcp_server_detail_derives_tool_count_from_orm_tools() -> None:
    server = McpServer(
        id=uuid4(),
        name="filesystem",
        transport="stdio",
        command="uvx",
        args=["mcp-server-filesystem"],
        env={},
        url=None,
        headers={},
        enabled=True,
        desired_state="running",
        runtime_status="running",
        last_checked_at=None,
        last_error=None,
        tools=[
            McpServerToolModel(
                id=uuid4(),
                name="search",
                description="Search files",
                input_schema={"type": "object"},
                discovered_at=datetime.now(UTC),
            ),
        ],
    )

    detail = McpServerDetail.model_validate(server)

    assert detail.tool_count == 1


def test_mcp_server_create_strips_stdio_command() -> None:
    server = McpServerCreate(
        name="filesystem",
        transport=McpTransport.stdio,
        command=" uvx ",
    )

    assert server.command == "uvx"

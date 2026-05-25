from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.mcp import (
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

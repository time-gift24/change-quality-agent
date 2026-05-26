from app.models.mcp import McpServer, McpServerTool
from app.models.runs import Run, RunEvent


def test_run_model_table_name() -> None:
    assert Run.__tablename__ == "runs"


def test_run_model_has_queryable_subject_columns() -> None:
    columns = Run.__table__.columns

    assert "subject_type" in columns
    assert "subject_id" in columns
    assert "env_key" in columns


def test_run_event_model_table_name() -> None:
    assert RunEvent.__tablename__ == "run_events"


def test_mcp_server_model_table_name() -> None:
    assert McpServer.__tablename__ == "mcp_servers"


def test_mcp_server_model_has_status_columns() -> None:
    columns = McpServer.__table__.columns

    assert "enabled" in columns
    assert "desired_state" in columns
    assert "runtime_status" in columns
    assert "last_checked_at" in columns
    assert "last_error" in columns


def test_mcp_server_tool_model_table_name() -> None:
    assert McpServerTool.__tablename__ == "mcp_server_tools"

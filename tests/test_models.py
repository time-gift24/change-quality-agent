from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm.attributes import set_committed_value

from app.models.mcp import McpServer, McpServerTool
from app.models.runs import Run, RunEvent
from app.models.users import User


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


def test_user_model_table_name() -> None:
    assert User.__tablename__ == "users"


def test_user_model_has_expected_columns() -> None:
    columns = User.__table__.columns

    assert "account" in columns
    assert "refresh_token" in columns
    assert "is_admin" in columns
    assert "meta" in columns


def test_user_model_account_has_unique_index() -> None:
    index = next(
        index for index in User.__table__.indexes if index.name == "uq_users_account"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["account"]


def test_user_model_has_expected_nullability_and_defaults() -> None:
    columns = User.__table__.columns

    assert columns["account"].nullable is False
    assert columns["refresh_token"].nullable is False
    assert columns["is_admin"].nullable is False
    assert columns["is_admin"].default is not None
    assert columns["is_admin"].default.arg is False
    assert columns["is_admin"].server_default is not None
    assert columns["meta"].nullable is False
    assert columns["meta"].default is not None
    assert columns["meta"].server_default is not None


def test_user_model_meta_uses_mutable_jsonb() -> None:
    user = User(account="developer", refresh_token="token", meta={})
    set_committed_value(user, "meta", user.meta)

    assert isinstance(User.__table__.columns["meta"].type, JSONB)
    assert isinstance(user.meta, MutableDict)

    user.meta["source"] = "dev"

    assert inspect(user).modified is True
    assert inspect(user).attrs.meta.history.has_changes() is True

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm.attributes import set_committed_value

from app.models.mcp import McpServer, McpServerTool
from app.models.sop_quality_checks import SopQualityCheck, SopQualityEvent
from app.models.users import User


def test_sop_quality_check_model_table_name() -> None:
    assert SopQualityCheck.__tablename__ == "sop_quality_checks"


def test_sop_quality_check_has_subject_environment_columns() -> None:
    columns = SopQualityCheck.__table__.columns

    assert columns["sop_id"].nullable is False
    assert columns["env_key"].nullable is False
    assert columns["thread_id"].nullable is False
    assert columns["checkpoint_ns"].nullable is False
    assert columns["sop_snapshot"].nullable is False
    assert "env_snapshot" not in columns
    assert "input_snapshot" not in columns


def test_sop_quality_check_active_unique_index() -> None:
    index = next(
        index
        for index in SopQualityCheck.__table__.indexes
        if index.name == "uq_sop_quality_checks_active_subject_env"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["sop_id", "env_key"]
    where = str(index.dialect_options["postgresql"]["where"])
    assert "pending" in where
    assert "running" in where


def test_sop_quality_check_links_to_session() -> None:
    columns = SopQualityCheck.__table__.columns

    assert "session_id" in columns
    assert columns["session_id"].nullable is True
    foreign_keys = columns["session_id"].foreign_keys
    assert {fk.target_fullname for fk in foreign_keys} == {"sessions.id"}


def test_sop_quality_event_model_has_no_payload_column() -> None:
    columns = SopQualityEvent.__table__.columns

    assert SopQualityEvent.__tablename__ == "sop_quality_events"
    assert "payload" not in columns
    assert columns["check_id"].nullable is False
    assert columns["sequence"].nullable is False


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

from app.models.mcp import McpServer, McpServerTool
from app.models.provider_credentials import ProviderCredential
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


def test_provider_credential_model_table_name() -> None:
    assert ProviderCredential.__tablename__ == "provider_credentials"


def test_provider_credential_model_has_scope_and_secret_columns() -> None:
    columns = ProviderCredential.__table__.columns

    assert "credential_type" in columns
    assert "scope" in columns
    assert "owner_user_id" in columns
    assert "api_key_ciphertext" in columns
    assert "api_key_hint" in columns
    assert "is_active" in columns


def test_provider_credential_model_has_db_semantic_constraints() -> None:
    constraints = {
        constraint.name for constraint in ProviderCredential.__table__.constraints
    }

    assert "ck_provider_credentials_scope_owner" in constraints
    assert "ck_provider_credentials_type" in constraints
    assert "ck_provider_credentials_scope" in constraints


def test_provider_credential_model_has_expected_indexes() -> None:
    indexes = {index.name: index for index in ProviderCredential.__table__.indexes}

    user_index = indexes["uq_provider_credentials_user_active_name"]
    assert user_index.unique is True
    assert [column.name for column in user_index.columns] == [
        "credential_type",
        "owner_user_id",
        "name",
    ]
    user_predicate = str(user_index.dialect_options["postgresql"]["where"])
    assert "scope = 'user'" in user_predicate
    assert "is_active" in user_predicate

    global_index = indexes["uq_provider_credentials_global_active_name"]
    assert global_index.unique is True
    assert [column.name for column in global_index.columns] == [
        "credential_type",
        "name",
    ]
    global_predicate = str(global_index.dialect_options["postgresql"]["where"])
    assert "scope = 'global'" in global_predicate
    assert "is_active" in global_predicate

    lookup_index = indexes["ix_provider_credentials_lookup"]
    assert [column.name for column in lookup_index.columns] == [
        "credential_type",
        "scope",
        "owner_user_id",
        "is_active",
    ]


def test_provider_credential_model_maps_metadata_and_defaults() -> None:
    columns = ProviderCredential.__table__.columns

    assert ProviderCredential.metadata_.property.columns[0].name == "metadata"
    assert columns["metadata"].server_default is not None
    assert columns["is_active"].server_default is not None

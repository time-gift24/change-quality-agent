import ast
from pathlib import Path

BASE_MIGRATION_PATH = Path(
    "migrations/versions/20260525_0001_create_sop_quality_checks.py"
)
MIGRATION_0008 = Path(
    "migrations/versions/20260529_0008_create_sessions_messages.py"
)
MIGRATION_0009 = Path(
    "migrations/versions/20260529_0009_add_sop_quality_session_id.py"
)


def test_alembic_revision_ids_are_unique() -> None:
    revisions: dict[str, Path] = {}

    for path in Path("migrations/versions").glob("*.py"):
        module = ast.parse(path.read_text())
        revision = _string_assignment(module, "revision")

        assert revision is not None, f"{path} does not define revision"
        assert revision not in revisions, (
            f"{path} duplicates revision {revision} from {revisions[revision]}"
        )
        revisions[revision] = path


def test_alembic_revision_graph_has_single_head() -> None:
    revisions: set[str] = set()
    down_revisions: set[str] = set()

    for path in Path("migrations/versions").glob("*.py"):
        module = ast.parse(path.read_text())
        revision = _string_assignment(module, "revision")

        assert revision is not None, f"{path} does not define revision"
        revisions.add(revision)
        down_revisions.update(_down_revisions(module))

    heads = revisions - down_revisions
    assert heads == {"20260529_0009"}


def test_base_migration_creates_sop_quality_tables_only() -> None:
    module = ast.parse(BASE_MIGRATION_PATH.read_text())
    created_tables = _op_call_first_string_args(module, "create_table")
    legacy_events_table = "run_" + "events"

    assert "sop_quality_checks" in created_tables
    assert "sop_quality_events" in created_tables
    assert "runs" not in created_tables
    assert legacy_events_table not in created_tables


def test_base_migration_creates_sop_quality_indexes() -> None:
    module = ast.parse(BASE_MIGRATION_PATH.read_text())
    created_indexes = _op_call_first_string_args(module, "create_index")

    assert "uq_sop_quality_checks_active_subject_env" in created_indexes
    assert "uq_sop_quality_events_check_sequence" in created_indexes


def test_alembic_env_imports_sop_quality_models_for_metadata() -> None:
    module = ast.parse(Path("migrations/env.py").read_text())
    imported_models = _imported_names_from_module(module, "app.models")

    assert {"agents", "mcp", "sessions", "sop_quality_checks", "users"} <= imported_models
    assert "runs" not in imported_models


def test_sessions_migration_creates_transcript_tables() -> None:
    source = MIGRATION_0008.read_text()

    assert '"sessions"' in source
    assert '"messages"' in source
    assert "thread_id" in source
    assert "additional_kwargs" in source
    assert "uq_messages_session_sequence" in source
    assert "ix_messages_session_created_at" in source
    assert "user_id" not in source


def test_session_id_migration_links_sop_quality_to_sessions() -> None:
    source = MIGRATION_0009.read_text()

    assert "session_id" in source
    assert "sop_quality_checks" in source
    assert "sessions" in source
    assert "fk_sop_quality_checks_session_id" in source


def _string_assignment(module: ast.Module, name: str) -> str | None:
    for node in module.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != name:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None


def _down_revisions(module: ast.Module) -> set[str]:
    for node in module.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "down_revision":
            continue
        if isinstance(node.value, ast.Constant):
            return {node.value.value} if isinstance(node.value.value, str) else set()
        if isinstance(node.value, ast.Tuple | ast.List):
            return {
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
    return set()


def _op_call_first_string_args(module: ast.Module, function_name: str) -> set[str]:
    names: set[str] = set()

    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != function_name:
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "op":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            names.add(first_arg.value)

    return names


def _imported_names_from_module(module: ast.Module, module_name: str) -> set[str]:
    names: set[str] = set()

    for node in module.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != module_name:
            continue
        names.update(alias.name for alias in node.names)

    return names

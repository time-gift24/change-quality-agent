import ast
from pathlib import Path

BASE_MIGRATION_PATH = Path(
    "migrations/versions/20260525_0001_create_sop_quality_checks.py"
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
    assert heads == {"20260527_0007"}


def test_base_migration_creates_sop_quality_tables_only() -> None:
    module = ast.parse(BASE_MIGRATION_PATH.read_text())
    created_tables = _op_call_first_string_args(module, "create_table")

    assert "sop_quality_checks" in created_tables
    assert "sop_quality_events" in created_tables
    assert "runs" not in created_tables
    assert "run_events" not in created_tables


def test_base_migration_creates_sop_quality_indexes() -> None:
    module = ast.parse(BASE_MIGRATION_PATH.read_text())
    created_indexes = _op_call_first_string_args(module, "create_index")

    assert "uq_sop_quality_checks_active_subject_env" in created_indexes
    assert "uq_sop_quality_events_check_sequence" in created_indexes


def test_alembic_env_imports_sop_quality_models_for_metadata() -> None:
    module = ast.parse(Path("migrations/env.py").read_text())
    imported_models = _imported_names_from_module(module, "app.models")

    assert {"agents", "mcp", "sop_quality_checks", "users"} <= imported_models
    assert "runs" not in imported_models


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

import ast
from pathlib import Path


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


def _string_assignment(module: ast.Module, name: str) -> str | None:
    for node in module.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != name:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None

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
    assert heads == {"20260527_0006"}


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

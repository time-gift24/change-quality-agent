from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass(frozen=True)
class AnyAllowance:
    count: int
    reason: str


@dataclass(frozen=True)
class AnyUsage:
    path: Path
    count: int
    allowed: int
    reason: str | None = None


DEFAULT_ALLOWED_COUNTS = {
    Path("app/core/llm_models.py"): AnyAllowance(
        count=6,
        reason="LangChain model_config and private payload hook accept provider-specific values.",
    ),
    Path("app/schemas/llm_providers.py"): AnyAllowance(
        count=3,
        reason="Pydantic before-validator receives raw dict or ORM objects.",
    ),
    Path("app/schemas/mcp.py"): AnyAllowance(
        count=3,
        reason="Pydantic before-validator derives fields from raw dict or ORM objects.",
    ),
}


def main() -> int:
    root = Path.cwd()
    paths = list(_iter_python_files(root, (Path("app"), Path("tests"))))
    findings = find_disallowed_any(root, paths, allowed_counts=DEFAULT_ALLOWED_COUNTS)
    if not findings:
        return 0

    print("Disallowed typing.Any usage found:")
    for finding in findings:
        detail = f"{finding.path}: found {finding.count}, allowed {finding.allowed}"
        if finding.reason:
            detail = f"{detail} ({finding.reason})"
        print(f"- {detail}")
    return 1


def find_disallowed_any(
    root: Path,
    paths: list[Path],
    *,
    allowed_counts: dict[Path, AnyAllowance],
) -> list[AnyUsage]:
    findings: list[AnyUsage] = []
    for path in sorted(paths):
        relative_path = path.relative_to(root)
        count = _count_any_usages(path)
        allowance = allowed_counts.get(relative_path)
        allowed = allowance.count if allowance else 0
        if count > allowed:
            findings.append(
                AnyUsage(
                    path=relative_path,
                    count=count,
                    allowed=allowed,
                    reason=allowance.reason if allowance else None,
                )
            )
    return findings


def _iter_python_files(root: Path, directories: tuple[Path, ...]):
    for directory in directories:
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path


def _count_any_usages(path: Path) -> int:
    tree = ast.parse(path.read_text(), filename=str(path))
    visitor = _AnyUsageVisitor()
    visitor.visit(tree)
    return visitor.count


class _AnyUsageVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.count = 0

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "typing":
            self.count += sum(1 for alias in node.names if alias.name == "Any")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "Any":
            self.count += 1

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "Any" and isinstance(node.value, ast.Name):
            if node.value.id == "typing":
                self.count += 1
        self.generic_visit(node)


if __name__ == "__main__":
    sys.exit(main())

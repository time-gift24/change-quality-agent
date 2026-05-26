import re
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"
REVISION_RE = re.compile(r'^revision: str = "([^"]+)"$', re.MULTILINE)


def test_alembic_revision_ids_are_unique() -> None:
    revisions: dict[str, Path] = {}
    duplicates: list[str] = []

    for path in MIGRATIONS_DIR.glob("*.py"):
        match = REVISION_RE.search(path.read_text(encoding="utf-8"))
        assert match is not None, f"{path.name} does not define revision"
        revision = match.group(1)
        if revision in revisions:
            duplicates.append(revision)
        revisions[revision] = path

    assert duplicates == []

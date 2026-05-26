import ast
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _read_revision_id(path: Path) -> str | None:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "revision" and isinstance(node.value, ast.Constant):
                return node.value.value if isinstance(node.value.value, str) else None
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "revision" for target in node.targets):
                return node.value.value if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) else None
    return None


def test_alembic_revision_ids_are_unique() -> None:
    revisions: dict[str, Path] = {}
    duplicates: list[str] = []

    for path in MIGRATIONS_DIR.glob("*.py"):
        revision = _read_revision_id(path)
        assert revision is not None, f"{path.name} does not define revision"
        if revision in revisions:
            duplicates.append(revision)
        revisions[revision] = path

    assert duplicates == []


def test_provider_credentials_migration_exists() -> None:
    path = MIGRATIONS_DIR / "20260526_0004_create_provider_credentials.py"

    assert path.exists()

    migration = path.read_text(encoding="utf-8")
    assert 'revision: str = "20260526_0004"' in migration
    assert (
        'down_revision: str | Sequence[str] | None = "20260526_0003"' in migration
    )
    assert "ck_provider_credentials_scope_owner" in migration
    assert "ck_provider_credentials_type" in migration
    assert "ck_provider_credentials_scope" in migration
    assert "uq_provider_credentials_user_active_name" in migration
    assert "uq_provider_credentials_global_active_name" in migration
    assert "ix_provider_credentials_lookup" in migration
    assert '''server_default=sa.text("'{}'::jsonb")''' in migration
    assert 'server_default=sa.text("true")' in migration
    assert '''postgresql_where=sa.text("scope = 'user' AND is_active")''' in migration
    assert (
        '''postgresql_where=sa.text("scope = 'global' AND is_active")'''
        in migration
    )


def test_agent_provider_binding_migration_replaces_model() -> None:
    path = MIGRATIONS_DIR / "20260526_0005_replace_agent_version_model.py"

    assert path.exists()
    migration = path.read_text(encoding="utf-8")
    assert 'revision: str = "20260526_0005"' in migration
    assert 'down_revision: str | Sequence[str] | None = "20260526_0004"' in migration
    assert 'op.add_column("agent_versions"' in migration
    assert '"provider_id"' in migration
    assert 'op.drop_column("agent_versions", "model")' in migration

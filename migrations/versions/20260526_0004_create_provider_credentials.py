"""create provider credentials

Revision ID: 20260526_0004
Revises: 20260526_0003
Create Date: 2026-05-26

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260526_0004"
down_revision: str | Sequence[str] | None = "20260526_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_type", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("api_key_hint", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scope = 'user' AND owner_user_id IS NOT NULL) "
            "OR (scope = 'global' AND owner_user_id IS NULL)",
            name="ck_provider_credentials_scope_owner",
        ),
        sa.CheckConstraint(
            "credential_type IN ('llm_provider', 'api_key')",
            name="ck_provider_credentials_credential_type",
        ),
        sa.CheckConstraint(
            "scope IN ('user', 'global')",
            name="ck_provider_credentials_scope",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_provider_credentials_user_name_active",
        "provider_credentials",
        ["credential_type", "owner_user_id", "name"],
        unique=True,
        postgresql_where=sa.text("scope = 'user' AND is_active"),
    )
    op.create_index(
        "uq_provider_credentials_global_name_active",
        "provider_credentials",
        ["credential_type", "name"],
        unique=True,
        postgresql_where=sa.text("scope = 'global' AND is_active"),
    )
    op.create_index(
        "ix_provider_credentials_lookup",
        "provider_credentials",
        ["credential_type", "scope", "owner_user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_credentials_lookup", table_name="provider_credentials")
    op.drop_index(
        "uq_provider_credentials_global_name_active",
        table_name="provider_credentials",
    )
    op.drop_index(
        "uq_provider_credentials_user_name_active",
        table_name="provider_credentials",
    )
    op.drop_table("provider_credentials")

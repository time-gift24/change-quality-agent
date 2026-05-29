"""create agents

Revision ID: 20260526_0003
Revises: 20260526_0002
Create Date: 2026-05-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260526_0003"
down_revision: str | Sequence[str] | None = "20260526_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_agents_table()
    _create_agent_versions_table()
    _create_agent_versions_indexes()
    _create_agents_latest_version_foreign_key()


def _create_agents_table() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "draft_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("latest_version_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_agent_versions_table() -> None:
    op.create_table(
        "agent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column(
            "model_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "tool_allowlist",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "mcp_server_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("published_by", sa.Text(), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_agent_versions_indexes() -> None:
    op.create_index(
        "uq_agent_versions_agent_version",
        "agent_versions",
        ["agent_id", "version_number"],
        unique=True,
    )
    op.create_index(
        "ix_agent_versions_agent_published",
        "agent_versions",
        ["agent_id", "published_at"],
    )


def _create_agents_latest_version_foreign_key() -> None:
    op.create_foreign_key(
        "fk_agents_latest_version_id_agent_versions",
        "agents",
        "agent_versions",
        ["latest_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_agents_latest_version_id_agent_versions",
        "agents",
        type_="foreignkey",
    )
    op.drop_index("ix_agent_versions_agent_published", table_name="agent_versions")
    op.drop_index("uq_agent_versions_agent_version", table_name="agent_versions")
    op.drop_table("agent_versions")
    op.drop_table("agents")

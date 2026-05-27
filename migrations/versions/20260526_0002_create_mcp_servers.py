"""create mcp servers

Revision ID: 20260526_0002
Revises: 20260525_0001
Create Date: 2026-05-26

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260526_0002"
down_revision: str | Sequence[str] | None = "20260525_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column(
            "args",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "env",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "desired_state",
            sa.String(length=32),
            server_default=sa.text("'stopped'"),
            nullable=False,
        ),
        sa.Column(
            "runtime_status",
            sa.String(length=32),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_mcp_servers_name", "mcp_servers", ["name"], unique=True)
    op.create_index(
        "ix_mcp_servers_enabled_desired_state",
        "mcp_servers",
        ["enabled", "desired_state"],
    )

    op.create_table(
        "mcp_server_tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "input_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["mcp_servers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_mcp_server_tools_server_name",
        "mcp_server_tools",
        ["server_id", "name"],
        unique=True,
    )
    op.create_index(
        "ix_mcp_server_tools_server_id",
        "mcp_server_tools",
        ["server_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_server_tools_server_id", table_name="mcp_server_tools")
    op.drop_index("uq_mcp_server_tools_server_name", table_name="mcp_server_tools")
    op.drop_table("mcp_server_tools")
    op.drop_index("ix_mcp_servers_enabled_desired_state", table_name="mcp_servers")
    op.drop_index("uq_mcp_servers_name", table_name="mcp_servers")
    op.drop_table("mcp_servers")

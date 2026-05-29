"""create sop quality checks

Revision ID: 20260525_0001
Revises:
Create Date: 2026-05-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260525_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_sop_quality_checks_table()
    _create_sop_quality_checks_indexes()
    _create_sop_quality_events_table()
    _create_sop_quality_events_indexes()


def _create_sop_quality_checks_table() -> None:
    op.create_table(
        "sop_quality_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sop_id", sa.Text(), nullable=False),
        sa.Column("env_key", sa.Text(), nullable=False),
        sa.Column("graph_name", sa.Text(), nullable=False),
        sa.Column("graph_version", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), nullable=False),
        sa.Column("current_checkpoint_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quality_result", sa.Text(), nullable=True),
        sa.Column(
            "sop_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
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
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_sop_quality_checks_indexes() -> None:
    op.create_index(
        "uq_sop_quality_checks_active_subject_env",
        "sop_quality_checks",
        ["sop_id", "env_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index(
        "ix_sop_quality_checks_subject_history",
        "sop_quality_checks",
        ["sop_id", "env_key", "created_at"],
    )
    op.create_index(
        "ix_sop_quality_checks_env_history",
        "sop_quality_checks",
        ["env_key", "created_at"],
    )
    op.create_index(
        "ix_sop_quality_checks_status_updated",
        "sop_quality_checks",
        ["status", "updated_at"],
    )


def _create_sop_quality_events_table() -> None:
    op.create_table(
        "sop_quality_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("check_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("node", sa.Text(), nullable=True),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["check_id"], ["sop_quality_checks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_sop_quality_events_indexes() -> None:
    op.create_index(
        "uq_sop_quality_events_check_sequence",
        "sop_quality_events",
        ["check_id", "sequence"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_sop_quality_events_check_sequence", table_name="sop_quality_events"
    )
    op.drop_table("sop_quality_events")
    op.drop_index(
        "ix_sop_quality_checks_status_updated", table_name="sop_quality_checks"
    )
    op.drop_index("ix_sop_quality_checks_env_history", table_name="sop_quality_checks")
    op.drop_index(
        "ix_sop_quality_checks_subject_history", table_name="sop_quality_checks"
    )
    op.drop_index(
        "uq_sop_quality_checks_active_subject_env", table_name="sop_quality_checks"
    )
    op.drop_table("sop_quality_checks")

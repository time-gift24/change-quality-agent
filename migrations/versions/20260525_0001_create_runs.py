"""create runs

Revision ID: 20260525_0001
Revises:
Create Date: 2026-05-25

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260525_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("assistant_id", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("env_key", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active_conflict_key", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kwargs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_checkpoint_id", sa.Text(), nullable=True),
        sa.Column("current_node", sa.Text(), nullable=True),
        sa.Column(
            "completed_nodes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "subject_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("result_status", sa.Text(), nullable=True),
        sa.Column(
            "structured_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "raw_graph_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
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
    op.create_index(
        "uq_runs_active_conflict_key",
        "runs",
        ["active_conflict_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index(
        "uq_runs_active_sop_subject_env",
        "runs",
        ["subject_type", "subject_id", "env_key"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'running') AND subject_type = 'sop'"
        ),
    )
    op.create_index(
        "ix_runs_subject_history",
        "runs",
        ["subject_type", "subject_id", "env_key", "created_at"],
    )

    op.create_table(
        "run_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("node", sa.Text(), nullable=True),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_run_events_run_sequence",
        "run_events",
        ["run_id", "sequence"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_run_events_run_sequence", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_runs_subject_history", table_name="runs")
    op.drop_index("uq_runs_active_sop_subject_env", table_name="runs")
    op.drop_index("uq_runs_active_conflict_key", table_name="runs")
    op.drop_table("runs")

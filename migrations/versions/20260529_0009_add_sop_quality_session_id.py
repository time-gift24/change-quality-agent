"""add session_id to sop_quality_checks

Revision ID: 20260529_0009
Revises: 20260529_0008
Create Date: 2026-05-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260529_0009"
down_revision: str | Sequence[str] | None = "20260529_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sop_quality_checks",
        sa.Column("session_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sop_quality_checks_session_id",
        "sop_quality_checks",
        "sessions",
        ["session_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_sop_quality_checks_session_id",
        "sop_quality_checks",
        type_="foreignkey",
    )
    op.drop_column("sop_quality_checks", "session_id")

"""add agent provider key

Revision ID: 20260527_0005
Revises: 20260527_0004
Create Date: 2026-05-27

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260527_0005"
down_revision: str | Sequence[str] | None = "20260527_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_versions",
        sa.Column("provider_key", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_versions", "provider_key")

"""replace agent version model with provider binding

Revision ID: 20260526_0005
Revises: 20260526_0004
Create Date: 2026-05-26

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260526_0005"
down_revision: str | Sequence[str] | None = "20260526_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    provider_id_column = sa.Column(
        "provider_id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.add_column("agent_versions", provider_id_column)
    op.drop_column("agent_versions", "model")


def downgrade() -> None:
    model_column = sa.Column("model", sa.Text(), nullable=False)
    op.add_column("agent_versions", model_column)
    op.drop_column("agent_versions", "provider_id")

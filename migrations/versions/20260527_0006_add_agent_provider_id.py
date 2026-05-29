"""add agent provider id

Revision ID: 20260527_0006
Revises: 20260527_0005
Create Date: 2026-05-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_0006"
down_revision: str | Sequence[str] | None = "20260527_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_versions",
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_versions_provider_id_llm_providers",
        "agent_versions",
        "llm_providers",
        ["provider_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_agent_versions_provider_id_llm_providers",
        "agent_versions",
        type_="foreignkey",
    )
    op.drop_column("agent_versions", "provider_id")

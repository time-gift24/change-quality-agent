from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'user' AND owner_user_id IS NOT NULL) "
            "OR (scope = 'global' AND owner_user_id IS NULL)",
            name="ck_provider_credentials_scope_owner",
        ),
        CheckConstraint(
            "credential_type IN ('llm_provider', 'api_key')",
            name="ck_provider_credentials_type",
        ),
        CheckConstraint(
            "scope IN ('user', 'global')",
            name="ck_provider_credentials_scope",
        ),
        Index(
            "uq_provider_credentials_user_active_name",
            "credential_type",
            "owner_user_id",
            "name",
            unique=True,
            postgresql_where=text("scope = 'user' AND is_active"),
        ),
        Index(
            "uq_provider_credentials_global_active_name",
            "credential_type",
            "name",
            unique=True,
            postgresql_where=text("scope = 'global' AND is_active"),
        ),
        Index(
            "ix_provider_credentials_lookup",
            "credential_type",
            "scope",
            "owner_user_id",
            "is_active",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    base_url: Mapped[str | None] = mapped_column(Text)
    api_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hint: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_by: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

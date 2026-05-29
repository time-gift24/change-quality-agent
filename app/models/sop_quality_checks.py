from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SopQualityCheck(Base):
    __tablename__ = "sop_quality_checks"
    __table_args__ = (
        Index(
            "uq_sop_quality_checks_active_subject_env",
            "sop_id",
            "env_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
        Index(
            "ix_sop_quality_checks_subject_history",
            "sop_id",
            "env_key",
            "created_at",
        ),
        Index("ix_sop_quality_checks_env_history", "env_key", "created_at"),
        Index("ix_sop_quality_checks_status_updated", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    session_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sessions.id"),
        nullable=True,
    )
    sop_id: Mapped[str] = mapped_column(Text, nullable=False)
    env_key: Mapped[str] = mapped_column(Text, nullable=False)
    graph_name: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_ns: Mapped[str] = mapped_column(Text, nullable=False)
    current_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_result: Mapped[str | None] = mapped_column(Text)
    sop_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["SopQualityEvent"]] = relationship(
        back_populates="check",
        cascade="all, delete-orphan",
    )


class SopQualityEvent(Base):
    __tablename__ = "sop_quality_events"
    __table_args__ = (
        Index(
            "uq_sop_quality_events_check_sequence",
            "check_id",
            "sequence",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_id: Mapped[UUID] = mapped_column(
        ForeignKey("sop_quality_checks.id"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    node: Mapped[str | None] = mapped_column(Text)
    checkpoint_id: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    check: Mapped[SopQualityCheck] = relationship(back_populates="events")

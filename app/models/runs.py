from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index(
            "uq_runs_active_conflict_key",
            "active_conflict_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
        Index(
            "uq_runs_active_sop_subject_env",
            "subject_type",
            "subject_id",
            "env_key",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'running') AND subject_type = 'sop'"
            ),
        ),
        Index(
            "ix_runs_subject_history",
            "subject_type",
            "subject_id",
            "env_key",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_id: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    env_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_conflict_key: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
    )
    kwargs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    current_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    current_node: Mapped[str | None] = mapped_column(Text)
    completed_nodes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    subject_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    result_status: Mapped[str | None] = mapped_column(Text)
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_graph_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
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

    events: Mapped[list["RunEvent"]] = relationship(back_populates="run")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        Index("uq_run_events_run_sequence", "run_id", "sequence", unique=True),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    node: Mapped[str | None] = mapped_column(Text)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_id: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    run: Mapped[Run] = relationship(back_populates="events")

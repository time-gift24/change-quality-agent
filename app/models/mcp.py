from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class McpServer(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (
        Index("uq_mcp_servers_name", "name", unique=True),
        Index("ix_mcp_servers_enabled_desired_state", "enabled", "desired_state"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    command: Mapped[str | None] = mapped_column(Text)
    args: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    env: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    url: Mapped[str | None] = mapped_column(Text)
    headers: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    desired_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="stopped",
    )
    runtime_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    tools: Mapped[list["McpServerTool"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
    )


class McpServerTool(Base):
    __tablename__ = "mcp_server_tools"
    __table_args__ = (
        Index("uq_mcp_server_tools_server_name", "server_id", "name", unique=True),
        Index("ix_mcp_server_tools_server_id", "server_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    server: Mapped[McpServer] = relationship(back_populates="tools")

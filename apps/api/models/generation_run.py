import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base


class GenerationRun(Base):
    __tablename__ = "generation_runs"
    # Coverage.1a persists only completed runs because every failed run rolls
    # back. Failed or partial states need a future migration and lifecycle design.
    __table_args__ = (
        Index(
            "ix_generation_runs_tenant_store_week",
            "tenant_id",
            "store_id",
            "week_start",
        ),
        CheckConstraint(
            "status IN ('completed')",
            name="ck_generation_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id"),
        nullable=False,
        index=True,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="completed",
        server_default=text("'completed'"),
    )
    created_count: Mapped[int] = mapped_column(Integer, nullable=False)
    replaced_count: Mapped[int] = mapped_column(Integer, nullable=False)
    kept_matching_count: Mapped[int] = mapped_column(Integer, nullable=False)
    kept_conflict_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

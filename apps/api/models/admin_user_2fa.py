import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base


class AdminUser2FA(Base):
    __tablename__ = "admin_user_2fa"
    __table_args__ = (
        Index("ix_admin_user_2fa_user_id", "user_id", unique=True),
        Index("ix_admin_user_2fa_pending_expires_at", "pending_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    totp_secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret_nonce: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret_key_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    totp_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pending_secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_secret_nonce: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_secret_key_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    totp_last_used_time_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

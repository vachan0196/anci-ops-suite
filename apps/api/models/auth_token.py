import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base


AUTH_TOKEN_TYPES = ("password_reset", "email_verification", "recovery_code")


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index("ix_auth_tokens_token_hash", "token_hash", unique=True),
        Index("ix_auth_tokens_user_type_created", "user_id", "token_type", "created_at"),
        Index("ix_auth_tokens_type_expires", "token_type", "expires_at"),
        CheckConstraint(
            "token_type IN ('password_reset', 'email_verification', 'recovery_code')",
            name="ck_auth_tokens_token_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    token_type: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    consumed_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    consumed_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

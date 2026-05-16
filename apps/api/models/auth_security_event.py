import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base


AUTH_SECURITY_EVENT_TYPES = (
    "auth.session.issued",
    "auth.session.rotated",
    "auth.session.revoked",
    "auth.session.rejected",
    "auth.session.blocked_disabled_admin",
    "auth.session.blocked_disabled_employee",
    "auth.session.blocked_inactive_staff_profile",
    "auth.session.reuse_detected",
    "auth.session.revoked_by_family_reuse",
)

AUTH_SECURITY_REJECTION_REASONS = (
    "invalid",
    "revoked",
    "expired",
    "wrong_portal",
    "missing_csrf_header",
    "family_revoked",
)

AUTH_SECURITY_PORTALS = ("admin", "employee")


class AuthSecurityEvent(Base):
    __tablename__ = "auth_security_events"
    __table_args__ = (
        Index("ix_auth_security_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_auth_security_events_user_created", "user_id", "created_at"),
        Index("ix_auth_security_events_employee_created", "employee_account_id", "created_at"),
        Index(
            "ix_auth_security_events_type_reason_created",
            "event_type",
            "rejection_reason",
            "created_at",
        ),
        Index("ix_auth_security_events_ip_created", "ip_address", "created_at"),
        Index("ix_auth_security_events_auth_session_id", "auth_session_id"),
        CheckConstraint(
            "event_type IN ("
            "'auth.session.issued', "
            "'auth.session.rotated', "
            "'auth.session.revoked', "
            "'auth.session.rejected', "
            "'auth.session.blocked_disabled_admin', "
            "'auth.session.blocked_disabled_employee', "
            "'auth.session.blocked_inactive_staff_profile', "
            "'auth.session.reuse_detected', "
            "'auth.session.revoked_by_family_reuse'"
            ")",
            name="ck_auth_security_events_event_type",
        ),
        CheckConstraint(
            "portal IS NULL OR portal IN ('admin', 'employee')",
            name="ck_auth_security_events_portal",
        ),
        CheckConstraint(
            "("
            "event_type = 'auth.session.rejected' "
            "AND rejection_reason IN ("
            "'invalid', 'revoked', 'expired', 'wrong_portal', "
            "'missing_csrf_header', 'family_revoked'"
            ")"
            ") OR (event_type != 'auth.session.rejected' AND rejection_reason IS NULL)",
            name="ck_auth_security_events_rejection_reason",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    portal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    employee_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employee_accounts.id"),
        nullable=True,
    )
    auth_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_sessions.id"),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

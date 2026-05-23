"""phase q5 2a step up auth

Revision ID: 0030_phase_q5_2a_step_up_auth
Revises: 0029_phase_q5_1b_2fa_lifecycle_events
Create Date: 2026-05-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0030_phase_q5_2a_step_up_auth"
down_revision: str | None = "0029_phase_q5_1b_2fa_lifecycle_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


Q5_1B_EVENT_TYPES = (
    "auth.session.issued",
    "auth.session.rotated",
    "auth.session.revoked",
    "auth.session.rejected",
    "auth.session.blocked_disabled_admin",
    "auth.session.blocked_disabled_employee",
    "auth.session.blocked_inactive_staff_profile",
    "auth.session.reuse_detected",
    "auth.session.revoked_by_family_reuse",
    "auth.password_reset.requested",
    "auth.password_reset.completed",
    "auth.password_reset.token_rejected",
    "auth.password_reset.session_revoked",
    "auth.email_verification.requested",
    "auth.email_verification.completed",
    "auth.email_verification.token_rejected",
    "auth.email_verification.already_verified",
    "auth.2fa.enrolment_started",
    "auth.2fa.enrolment_completed",
    "auth.2fa.enrolment_abandoned",
    "auth.2fa.verification_succeeded",
    "auth.2fa.verification_failed",
    "auth.2fa.recovery_code_used",
    "auth.2fa.disabled",
    "auth.2fa.recovery_codes_regenerated",
)

Q5_2A_EVENT_TYPES = Q5_1B_EVENT_TYPES + (
    "auth.2fa.step_up_succeeded",
    "auth.2fa.step_up_failed",
    "auth.sensitive_action.blocked",
    "auth.sensitive_action.allowed",
)


def _event_type_check(event_types: tuple[str, ...]) -> str:
    values = ", ".join(f"'{event_type}'" for event_type in event_types)
    return f"event_type IN ({values})"


Q5_1B_REJECTION_REASON_CHECK = (
    "("
    "event_type = 'auth.session.rejected' "
    "AND rejection_reason IN ("
    "'invalid', 'revoked', 'expired', 'wrong_portal', "
    "'missing_csrf_header', 'family_revoked'"
    ")"
    ") OR ("
    "event_type = 'auth.password_reset.token_rejected' "
    "AND rejection_reason IN ('invalid', 'expired', 'used', 'wrong_type')"
    ") OR ("
    "event_type = 'auth.email_verification.token_rejected' "
    "AND rejection_reason IN ('invalid', 'expired', 'used', 'wrong_type')"
    ") OR ("
    "event_type = 'auth.2fa.verification_failed' "
    "AND rejection_reason IN ("
    "'invalid_code', 'code_reused', 'expired_window', "
    "'rate_limited', 'challenge_expired', 'challenge_invalid'"
    ")"
    ") OR ("
    "event_type NOT IN ("
    "'auth.session.rejected', "
    "'auth.password_reset.token_rejected', "
    "'auth.email_verification.token_rejected', "
    "'auth.2fa.verification_failed'"
    ") "
    "AND rejection_reason IS NULL"
    ")"
)

Q5_2A_REJECTION_REASON_CHECK = (
    "("
    "event_type = 'auth.session.rejected' "
    "AND rejection_reason IN ("
    "'invalid', 'revoked', 'expired', 'wrong_portal', "
    "'missing_csrf_header', 'family_revoked'"
    ")"
    ") OR ("
    "event_type = 'auth.password_reset.token_rejected' "
    "AND rejection_reason IN ('invalid', 'expired', 'used', 'wrong_type')"
    ") OR ("
    "event_type = 'auth.email_verification.token_rejected' "
    "AND rejection_reason IN ('invalid', 'expired', 'used', 'wrong_type')"
    ") OR ("
    "event_type = 'auth.2fa.verification_failed' "
    "AND rejection_reason IN ("
    "'invalid_code', 'code_reused', 'expired_window', "
    "'rate_limited', 'challenge_expired', 'challenge_invalid'"
    ")"
    ") OR ("
    "event_type = 'auth.2fa.step_up_failed' "
    "AND rejection_reason IN ("
    "'invalid_code', 'code_reused', 'expired_window', "
    "'rate_limited', 'challenge_expired', 'challenge_invalid'"
    ")"
    ") OR ("
    "event_type NOT IN ("
    "'auth.session.rejected', "
    "'auth.password_reset.token_rejected', "
    "'auth.email_verification.token_rejected', "
    "'auth.2fa.verification_failed', "
    "'auth.2fa.step_up_failed'"
    ") "
    "AND rejection_reason IS NULL"
    ")"
)


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column("last_2fa_step_up_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        _event_type_check(Q5_2A_EVENT_TYPES),
    )
    op.drop_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
        Q5_2A_REJECTION_REASON_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        _event_type_check(Q5_1B_EVENT_TYPES),
    )
    op.drop_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
        Q5_1B_REJECTION_REASON_CHECK,
    )
    op.drop_column("auth_sessions", "last_2fa_step_up_at")

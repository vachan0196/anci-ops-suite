"""phase q5 1b 2fa lifecycle events

Revision ID: 0029_phase_q5_1b_2fa_lifecycle_events
Revises: 0028_phase_q5_1_totp_2fa
Create Date: 2026-05-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0029_phase_q5_1b_2fa_lifecycle_events"
down_revision: Union[str, Sequence[str], None] = "0028_phase_q5_1_totp_2fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


Q5_1B_EVENT_TYPES = (
    "'auth.session.issued', "
    "'auth.session.rotated', "
    "'auth.session.revoked', "
    "'auth.session.rejected', "
    "'auth.session.blocked_disabled_admin', "
    "'auth.session.blocked_disabled_employee', "
    "'auth.session.blocked_inactive_staff_profile', "
    "'auth.session.reuse_detected', "
    "'auth.session.revoked_by_family_reuse', "
    "'auth.password_reset.requested', "
    "'auth.password_reset.completed', "
    "'auth.password_reset.token_rejected', "
    "'auth.password_reset.session_revoked', "
    "'auth.email_verification.requested', "
    "'auth.email_verification.completed', "
    "'auth.email_verification.token_rejected', "
    "'auth.email_verification.already_verified', "
    "'auth.2fa.enrolment_started', "
    "'auth.2fa.enrolment_completed', "
    "'auth.2fa.enrolment_abandoned', "
    "'auth.2fa.verification_succeeded', "
    "'auth.2fa.verification_failed', "
    "'auth.2fa.recovery_code_used', "
    "'auth.2fa.disabled', "
    "'auth.2fa.recovery_codes_regenerated'"
)

Q5_1_EVENT_TYPES = (
    "'auth.session.issued', "
    "'auth.session.rotated', "
    "'auth.session.revoked', "
    "'auth.session.rejected', "
    "'auth.session.blocked_disabled_admin', "
    "'auth.session.blocked_disabled_employee', "
    "'auth.session.blocked_inactive_staff_profile', "
    "'auth.session.reuse_detected', "
    "'auth.session.revoked_by_family_reuse', "
    "'auth.password_reset.requested', "
    "'auth.password_reset.completed', "
    "'auth.password_reset.token_rejected', "
    "'auth.password_reset.session_revoked', "
    "'auth.email_verification.requested', "
    "'auth.email_verification.completed', "
    "'auth.email_verification.token_rejected', "
    "'auth.email_verification.already_verified', "
    "'auth.2fa.enrolment_started', "
    "'auth.2fa.enrolment_completed', "
    "'auth.2fa.enrolment_abandoned', "
    "'auth.2fa.verification_succeeded', "
    "'auth.2fa.verification_failed', "
    "'auth.2fa.recovery_code_used'"
)


def _create_event_type_constraint(event_types: str) -> None:
    op.create_check_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        f"event_type IN ({event_types})",
    )


def upgrade() -> None:
    op.drop_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        type_="check",
    )
    _create_event_type_constraint(Q5_1B_EVENT_TYPES)


def downgrade() -> None:
    op.drop_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        type_="check",
    )
    _create_event_type_constraint(Q5_1_EVENT_TYPES)

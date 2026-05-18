"""phase q4 3 email verification

Revision ID: 0026_phase_q4_3_email_verified_at
Revises: 0025_phase_q4_2_auth_tokens
Create Date: 2026-05-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0026_phase_q4_3_email_verified_at"
down_revision: Union[str, Sequence[str], None] = "0025_phase_q4_2_auth_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        "event_type IN ("
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
        "'auth.email_verification.already_verified'"
        ")",
    )
    op.create_check_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
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
        "event_type NOT IN ("
        "'auth.session.rejected', "
        "'auth.password_reset.token_rejected', "
        "'auth.email_verification.token_rejected'"
        ") "
        "AND rejection_reason IS NULL"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        "event_type IN ("
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
        "'auth.password_reset.session_revoked'"
        ")",
    )
    op.create_check_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
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
        "event_type NOT IN ('auth.session.rejected', 'auth.password_reset.token_rejected') "
        "AND rejection_reason IS NULL"
        ")",
    )
    op.drop_column("users", "email_verified_at")

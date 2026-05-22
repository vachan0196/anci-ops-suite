"""phase q5 1 totp 2fa

Revision ID: 0028_phase_q5_1_totp_2fa
Revises: 0027_phase_q4_4_owner_role
Create Date: 2026-05-21 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0028_phase_q5_1_totp_2fa"
down_revision: Union[str, Sequence[str], None] = "0027_phase_q4_4_owner_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


Q4_3_EVENT_TYPES = (
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
)


def _create_q5_1_auth_security_constraints() -> None:
    op.create_check_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        f"event_type IN ({Q5_1_EVENT_TYPES})",
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
        ")",
    )


def _create_q4_3_auth_security_constraints() -> None:
    op.create_check_constraint(
        "ck_auth_security_events_event_type",
        "auth_security_events",
        f"event_type IN ({Q4_3_EVENT_TYPES})",
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


def upgrade() -> None:
    op.create_table(
        "admin_user_2fa",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("totp_secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("totp_secret_nonce", sa.Text(), nullable=True),
        sa.Column("totp_secret_key_version", sa.Integer(), nullable=True),
        sa.Column("totp_enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("pending_secret_nonce", sa.Text(), nullable=True),
        sa.Column("pending_secret_key_version", sa.Integer(), nullable=True),
        sa.Column("pending_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("totp_last_used_time_step", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_user_2fa_user_id", "admin_user_2fa", ["user_id"], unique=True)
    op.create_index(
        "ix_admin_user_2fa_pending_expires_at",
        "admin_user_2fa",
        ["pending_expires_at"],
        unique=False,
    )

    op.create_table(
        "auth_2fa_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("challenge_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_address_hash", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_2fa_challenges_challenge_hash",
        "auth_2fa_challenges",
        ["challenge_hash"],
        unique=True,
    )
    op.create_index(
        "ix_auth_2fa_challenges_user_created",
        "auth_2fa_challenges",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_2fa_challenges_expires_at",
        "auth_2fa_challenges",
        ["expires_at"],
        unique=False,
    )

    op.drop_constraint("ck_auth_tokens_token_type", "auth_tokens", type_="check")
    op.alter_column("auth_tokens", "expires_at", nullable=True)
    op.create_check_constraint(
        "ck_auth_tokens_token_type",
        "auth_tokens",
        "token_type IN ('password_reset', 'email_verification', 'recovery_code')",
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
    _create_q5_1_auth_security_constraints()


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
    _create_q4_3_auth_security_constraints()

    op.drop_constraint("ck_auth_tokens_token_type", "auth_tokens", type_="check")
    op.execute("DELETE FROM auth_tokens WHERE token_type = 'recovery_code'")
    op.alter_column("auth_tokens", "expires_at", nullable=False)
    op.create_check_constraint(
        "ck_auth_tokens_token_type",
        "auth_tokens",
        "token_type IN ('password_reset', 'email_verification')",
    )

    op.drop_index("ix_auth_2fa_challenges_expires_at", table_name="auth_2fa_challenges")
    op.drop_index("ix_auth_2fa_challenges_user_created", table_name="auth_2fa_challenges")
    op.drop_index("ix_auth_2fa_challenges_challenge_hash", table_name="auth_2fa_challenges")
    op.drop_table("auth_2fa_challenges")

    op.drop_index("ix_admin_user_2fa_pending_expires_at", table_name="admin_user_2fa")
    op.drop_index("ix_admin_user_2fa_user_id", table_name="admin_user_2fa")
    op.drop_table("admin_user_2fa")

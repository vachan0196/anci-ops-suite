"""phase q4 2 auth tokens

Revision ID: 0025_phase_q4_2_auth_tokens
Revises: 0024_phase_q3_3_session_family
Create Date: 2026-05-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0025_phase_q4_2_auth_tokens"
down_revision: Union[str, Sequence[str], None] = "0024_phase_q3_3_session_family"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_type", sa.Text(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_ip", sa.Text(), nullable=True),
        sa.Column("consumed_ip", sa.Text(), nullable=True),
        sa.Column("created_user_agent", sa.Text(), nullable=True),
        sa.Column("consumed_user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "token_type IN ('password_reset', 'email_verification')",
            name="ck_auth_tokens_token_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)
    op.create_index(
        "ix_auth_tokens_user_type_created",
        "auth_tokens",
        ["user_id", "token_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_tokens_type_expires",
        "auth_tokens",
        ["token_type", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_type_expires", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_type_created", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_table("auth_tokens")

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
        "'auth.session.revoked_by_family_reuse'"
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
        ") OR (event_type != 'auth.session.rejected' AND rejection_reason IS NULL)",
    )

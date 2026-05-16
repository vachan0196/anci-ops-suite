"""phase q3 3 session family

Revision ID: 0024_phase_q3_3_session_family
Revises: 0023_phase_q3_2_1_auth_security_events
Create Date: 2026-05-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0024_phase_q3_3_session_family"
down_revision: Union[str, Sequence[str], None] = "0023_phase_q3_2_1_auth_security_events"
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

    op.add_column(
        "auth_sessions",
        sa.Column("session_family_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "auth_sessions",
        sa.Column("parent_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "auth_sessions",
        sa.Column("reuse_detected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_auth_sessions_parent_session_id",
        "auth_sessions",
        "auth_sessions",
        ["parent_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_auth_sessions_session_family_id",
        "auth_sessions",
        ["session_family_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "UPDATE auth_sessions "
            "SET is_revoked = true, revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP) "
            "WHERE is_revoked = false"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_session_family_id", table_name="auth_sessions")
    op.drop_constraint(
        "fk_auth_sessions_parent_session_id",
        "auth_sessions",
        type_="foreignkey",
    )
    op.drop_column("auth_sessions", "reuse_detected_at")
    op.drop_column("auth_sessions", "parent_session_id")
    op.drop_column("auth_sessions", "session_family_id")
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
        "'auth.session.blocked_inactive_staff_profile'"
        ")",
    )
    op.create_check_constraint(
        "ck_auth_security_events_rejection_reason",
        "auth_security_events",
        "("
        "event_type = 'auth.session.rejected' "
        "AND rejection_reason IN ("
        "'invalid', 'revoked', 'expired', 'wrong_portal', 'missing_csrf_header'"
        ")"
        ") OR (event_type != 'auth.session.rejected' AND rejection_reason IS NULL)",
    )

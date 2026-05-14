"""phase q3 2 1 auth security events

Revision ID: 0023_phase_q3_2_1_auth_security_events
Revises: 0022_phase_q2_auth_sessions
Create Date: 2026-05-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0023_phase_q3_2_1_auth_security_events"
down_revision: Union[str, Sequence[str], None] = "0022_phase_q2_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("rejection_reason", sa.String(length=32), nullable=True),
        sa.Column("portal", sa.String(length=32), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("auth_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "event_type IN ("
            "'auth.session.issued', "
            "'auth.session.rotated', "
            "'auth.session.revoked', "
            "'auth.session.rejected', "
            "'auth.session.blocked_disabled_admin', "
            "'auth.session.blocked_disabled_employee', "
            "'auth.session.blocked_inactive_staff_profile'"
            ")",
            name="ck_auth_security_events_event_type",
        ),
        sa.CheckConstraint(
            "portal IS NULL OR portal IN ('admin', 'employee')",
            name="ck_auth_security_events_portal",
        ),
        sa.CheckConstraint(
            "("
            "event_type = 'auth.session.rejected' "
            "AND rejection_reason IN ("
            "'invalid', 'revoked', 'expired', 'wrong_portal', 'missing_csrf_header'"
            ")"
            ") OR (event_type != 'auth.session.rejected' AND rejection_reason IS NULL)",
            name="ck_auth_security_events_rejection_reason",
        ),
        sa.ForeignKeyConstraint(["auth_session_id"], ["auth_sessions.id"]),
        sa.ForeignKeyConstraint(["employee_account_id"], ["employee_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_security_events_tenant_created",
        "auth_security_events",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_security_events_user_created",
        "auth_security_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_security_events_employee_created",
        "auth_security_events",
        ["employee_account_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_security_events_type_reason_created",
        "auth_security_events",
        ["event_type", "rejection_reason", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_security_events_ip_created",
        "auth_security_events",
        ["ip_address", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_security_events_auth_session_id",
        "auth_security_events",
        ["auth_session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_security_events_auth_session_id", table_name="auth_security_events")
    op.drop_index("ix_auth_security_events_ip_created", table_name="auth_security_events")
    op.drop_index("ix_auth_security_events_type_reason_created", table_name="auth_security_events")
    op.drop_index("ix_auth_security_events_employee_created", table_name="auth_security_events")
    op.drop_index("ix_auth_security_events_user_created", table_name="auth_security_events")
    op.drop_index("ix_auth_security_events_tenant_created", table_name="auth_security_events")
    op.drop_table("auth_security_events")

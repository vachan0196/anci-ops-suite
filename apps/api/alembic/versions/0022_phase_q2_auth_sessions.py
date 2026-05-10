"""phase q2 auth sessions

Revision ID: 0022_phase_q2_auth_sessions
Revises: 0021_phase_p4_swap_target_shift
Create Date: 2026-05-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0022_phase_q2_auth_sessions"
down_revision: Union[str, Sequence[str], None] = "0021_phase_p4_swap_target_shift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("portal", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["employee_account_id"], ["employee_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_employee_account_id", "auth_sessions", ["employee_account_id"], unique=False)
    op.create_index("ix_auth_sessions_portal_token_hash", "auth_sessions", ["portal", "token_hash"], unique=False)
    op.create_index("ix_auth_sessions_tenant_id", "auth_sessions", ["tenant_id"], unique=False)
    op.create_index("ix_auth_sessions_tenant_id_portal", "auth_sessions", ["tenant_id", "portal"], unique=False)
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=False)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_tenant_id_portal", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_tenant_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_portal_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_employee_account_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

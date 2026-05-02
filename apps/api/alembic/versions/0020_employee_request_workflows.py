"""add employee request workflow fields

Revision ID: 0020_employee_request_workflows
Revises: 0019_employee_availability_foundation
Create Date: 2026-05-01 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0020_employee_request_workflows"
down_revision: Union[str, Sequence[str], None] = "0019_employee_availability_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("shift_requests", "shift_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("shift_requests", sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "shift_requests",
        sa.Column("requester_employee_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "shift_requests",
        sa.Column("target_employee_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("shift_requests", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("shift_requests", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("shift_requests", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("shift_requests", sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("shift_requests", sa.Column("approval_reason", sa.Text(), nullable=True))
    op.add_column("shift_requests", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("shift_requests", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shift_requests", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shift_requests", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_shift_requests_site_id_stores",
        "shift_requests",
        "stores",
        ["site_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_shift_requests_requester_employee_account_id",
        "shift_requests",
        "employee_accounts",
        ["requester_employee_account_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_shift_requests_target_employee_account_id",
        "shift_requests",
        "employee_accounts",
        ["target_employee_account_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_shift_requests_approver_user_id_users",
        "shift_requests",
        "users",
        ["approver_user_id"],
        ["id"],
    )
    op.create_index("ix_shift_requests_site_id", "shift_requests", ["site_id"], unique=False)
    op.create_index(
        "ix_shift_requests_requester_employee_account_id",
        "shift_requests",
        ["requester_employee_account_id"],
        unique=False,
    )
    op.create_index(
        "ix_shift_requests_target_employee_account_id",
        "shift_requests",
        ["target_employee_account_id"],
        unique=False,
    )
    op.create_index("ix_shift_requests_approver_user_id", "shift_requests", ["approver_user_id"], unique=False)
    op.create_index(
        "ix_shift_requests_tenant_site_requester_employee",
        "shift_requests",
        ["tenant_id", "site_id", "requester_employee_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shift_requests_tenant_site_requester_employee", table_name="shift_requests")
    op.drop_index("ix_shift_requests_approver_user_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_target_employee_account_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_requester_employee_account_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_site_id", table_name="shift_requests")
    op.drop_constraint("fk_shift_requests_approver_user_id_users", "shift_requests", type_="foreignkey")
    op.drop_constraint("fk_shift_requests_target_employee_account_id", "shift_requests", type_="foreignkey")
    op.drop_constraint("fk_shift_requests_requester_employee_account_id", "shift_requests", type_="foreignkey")
    op.drop_constraint("fk_shift_requests_site_id_stores", "shift_requests", type_="foreignkey")
    op.drop_column("shift_requests", "cancelled_at")
    op.drop_column("shift_requests", "updated_at")
    op.drop_column("shift_requests", "decided_at")
    op.drop_column("shift_requests", "rejection_reason")
    op.drop_column("shift_requests", "approval_reason")
    op.drop_column("shift_requests", "approver_user_id")
    op.drop_column("shift_requests", "end_date")
    op.drop_column("shift_requests", "start_date")
    op.drop_column("shift_requests", "reason")
    op.drop_column("shift_requests", "target_employee_account_id")
    op.drop_column("shift_requests", "requester_employee_account_id")
    op.drop_column("shift_requests", "site_id")
    op.alter_column("shift_requests", "shift_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

"""add canonical availability uniqueness and source

Revision ID: 0033_admin_staff_availability_week
Revises: 0032_store_email_notes
Create Date: 2026-06-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0033_admin_staff_availability_week"
down_revision: str | None = "0032_store_email_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_availability_entries_employee_slot_type",
        "availability_entries",
        type_="unique",
    )
    op.add_column("availability_entries", sa.Column("source", sa.String(length=32), nullable=True))
    op.create_index(
        "uq_availability_entries_tenant_user_date_type_full_day",
        "availability_entries",
        ["tenant_id", "user_id", "date", "type"],
        unique=True,
        postgresql_where=sa.text("start_time IS NULL AND end_time IS NULL"),
    )
    op.create_index(
        "uq_availability_entries_tenant_user_date_time_type",
        "availability_entries",
        ["tenant_id", "user_id", "date", "start_time", "end_time", "type"],
        unique=True,
        postgresql_where=sa.text("start_time IS NOT NULL AND end_time IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_availability_entries_tenant_user_date_time_type", table_name="availability_entries")
    op.drop_index("uq_availability_entries_tenant_user_date_type_full_day", table_name="availability_entries")
    op.drop_column("availability_entries", "source")
    op.create_unique_constraint(
        "uq_availability_entries_employee_slot_type",
        "availability_entries",
        ["tenant_id", "site_id", "employee_account_id", "date", "start_time", "end_time", "type"],
    )

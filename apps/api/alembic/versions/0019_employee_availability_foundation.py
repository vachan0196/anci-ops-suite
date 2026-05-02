"""add employee-scoped availability fields

Revision ID: 0019_employee_availability_foundation
Revises: 0018_employee_accounts
Create Date: 2026-05-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0019_employee_availability_foundation"
down_revision: Union[str, Sequence[str], None] = "0018_employee_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("availability_entries", sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "availability_entries",
        sa.Column("employee_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("availability_entries", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_availability_entries_site_id_stores",
        "availability_entries",
        "stores",
        ["site_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_availability_entries_employee_account_id",
        "availability_entries",
        "employee_accounts",
        ["employee_account_id"],
        ["id"],
    )
    op.create_index("ix_availability_entries_site_id", "availability_entries", ["site_id"], unique=False)
    op.create_index(
        "ix_availability_entries_employee_account_id",
        "availability_entries",
        ["employee_account_id"],
        unique=False,
    )
    op.create_index(
        "ix_availability_entries_tenant_site_employee_week",
        "availability_entries",
        ["tenant_id", "site_id", "employee_account_id", "week_start"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_availability_entries_employee_slot_type",
        "availability_entries",
        ["tenant_id", "site_id", "employee_account_id", "date", "start_time", "end_time", "type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_availability_entries_employee_slot_type", "availability_entries", type_="unique")
    op.drop_index("ix_availability_entries_tenant_site_employee_week", table_name="availability_entries")
    op.drop_index("ix_availability_entries_employee_account_id", table_name="availability_entries")
    op.drop_index("ix_availability_entries_site_id", table_name="availability_entries")
    op.drop_constraint("fk_availability_entries_employee_account_id", "availability_entries", type_="foreignkey")
    op.drop_constraint("fk_availability_entries_site_id_stores", "availability_entries", type_="foreignkey")
    op.drop_column("availability_entries", "updated_at")
    op.drop_column("availability_entries", "employee_account_id")
    op.drop_column("availability_entries", "site_id")

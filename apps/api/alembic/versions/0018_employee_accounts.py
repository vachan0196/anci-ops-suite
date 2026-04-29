"""add employee accounts

Revision ID: 0018_employee_accounts
Revises: 0017_store_opening_hours_settings
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0018_employee_accounts"
down_revision: Union[str, Sequence[str], None] = "0017_store_opening_hours_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "store_id", "username", name="uq_employee_accounts_tenant_store_username"),
    )
    op.create_index("ix_employee_accounts_tenant_id", "employee_accounts", ["tenant_id"], unique=False)
    op.create_index("ix_employee_accounts_store_id", "employee_accounts", ["store_id"], unique=False)
    op.create_index(
        "ix_employee_accounts_tenant_id_store_id",
        "employee_accounts",
        ["tenant_id", "store_id"],
        unique=False,
    )

    op.add_column(
        "staff_profiles",
        sa.Column("employee_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_staff_profiles_employee_account_id", "staff_profiles", ["employee_account_id"], unique=False)
    op.create_foreign_key(
        "fk_staff_profiles_employee_account_id_employee_accounts",
        "staff_profiles",
        "employee_accounts",
        ["employee_account_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_staff_profiles_employee_account_id_employee_accounts",
        "staff_profiles",
        type_="foreignkey",
    )
    op.drop_index("ix_staff_profiles_employee_account_id", table_name="staff_profiles")
    op.drop_column("staff_profiles", "employee_account_id")

    op.drop_index("ix_employee_accounts_tenant_id_store_id", table_name="employee_accounts")
    op.drop_index("ix_employee_accounts_store_id", table_name="employee_accounts")
    op.drop_index("ix_employee_accounts_tenant_id", table_name="employee_accounts")
    op.drop_table("employee_accounts")

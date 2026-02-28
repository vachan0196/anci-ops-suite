"""add stores and staff profiles

Revision ID: 0004_operational_domain_stores_staff
Revises: 0003_tenant_isolation_and_audit_logs
Create Date: 2026-02-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_operational_domain_stores_staff"
down_revision: Union[str, Sequence[str], None] = "0003_tenant_isolation_and_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stores_tenant_id", "stores", ["tenant_id"], unique=False)
    op.create_index("ix_stores_tenant_id_is_active", "stores", ["tenant_id", "is_active"], unique=False)
    op.create_index(
        "uq_stores_tenant_id_code_not_null",
        "stores",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )

    op.create_table(
        "staff_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_staff_profiles_tenant_user"),
    )
    op.create_index("ix_staff_profiles_tenant_id", "staff_profiles", ["tenant_id"], unique=False)
    op.create_index("ix_staff_profiles_user_id", "staff_profiles", ["user_id"], unique=False)
    op.create_index("ix_staff_profiles_store_id", "staff_profiles", ["store_id"], unique=False)
    op.create_index(
        "ix_staff_profiles_tenant_id_store_id",
        "staff_profiles",
        ["tenant_id", "store_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_staff_profiles_tenant_id_store_id", table_name="staff_profiles")
    op.drop_index("ix_staff_profiles_store_id", table_name="staff_profiles")
    op.drop_index("ix_staff_profiles_user_id", table_name="staff_profiles")
    op.drop_index("ix_staff_profiles_tenant_id", table_name="staff_profiles")
    op.drop_table("staff_profiles")

    op.drop_index("uq_stores_tenant_id_code_not_null", table_name="stores")
    op.drop_index("ix_stores_tenant_id_is_active", table_name="stores")
    op.drop_index("ix_stores_tenant_id", table_name="stores")
    op.drop_table("stores")

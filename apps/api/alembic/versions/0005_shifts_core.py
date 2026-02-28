"""add shifts core table

Revision ID: 0005_shifts_core
Revises: 0004_operational_domain_stores_staff
Create Date: 2026-02-27 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_shifts_core"
down_revision: Union[str, Sequence[str], None] = "0004_operational_domain_stores_staff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shifts_tenant_id", "shifts", ["tenant_id"], unique=False)
    op.create_index("ix_shifts_store_id", "shifts", ["store_id"], unique=False)
    op.create_index("ix_shifts_assigned_user_id", "shifts", ["assigned_user_id"], unique=False)
    op.create_index("ix_shifts_tenant_id_store_id", "shifts", ["tenant_id", "store_id"], unique=False)
    op.create_index(
        "ix_shifts_tenant_id_assigned_user_id",
        "shifts",
        ["tenant_id", "assigned_user_id"],
        unique=False,
    )
    op.create_index("ix_shifts_tenant_id_start_at", "shifts", ["tenant_id", "start_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shifts_tenant_id_start_at", table_name="shifts")
    op.drop_index("ix_shifts_tenant_id_assigned_user_id", table_name="shifts")
    op.drop_index("ix_shifts_tenant_id_store_id", table_name="shifts")
    op.drop_index("ix_shifts_assigned_user_id", table_name="shifts")
    op.drop_index("ix_shifts_store_id", table_name="shifts")
    op.drop_index("ix_shifts_tenant_id", table_name="shifts")
    op.drop_table("shifts")

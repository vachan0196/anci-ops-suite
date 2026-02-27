"""add tenant isolation and audit logs

Revision ID: 0003_tenant_isolation_and_audit_logs
Revises: 0003_widen_alembic_version
Create Date: 2026-02-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_tenant_isolation_and_audit_logs"
down_revision: Union[str, Sequence[str], None] = "0003_widen_alembic_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hot_food_demand_inputs",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_hot_food_demand_inputs_tenant_id_tenants",
        "hot_food_demand_inputs",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(
        "ix_hot_food_demand_inputs_tenant_id",
        "hot_food_demand_inputs",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"], unique=False)
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_hot_food_demand_inputs_tenant_id", table_name="hot_food_demand_inputs")
    op.drop_constraint("fk_hot_food_demand_inputs_tenant_id_tenants", "hot_food_demand_inputs", type_="foreignkey")
    op.drop_column("hot_food_demand_inputs", "tenant_id")

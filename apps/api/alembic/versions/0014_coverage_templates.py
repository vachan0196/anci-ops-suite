"""add coverage templates table

Revision ID: 0014_coverage_templates
Revises: 0013_staff_profile_details
Create Date: 2026-03-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0014_coverage_templates"
down_revision: Union[str, Sequence[str], None] = "0013_staff_profile_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coverage_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("required_headcount", sa.Integer(), nullable=False),
        sa.Column("required_role", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_coverage_templates_day_of_week_range"),
        sa.CheckConstraint("required_headcount >= 1", name="ck_coverage_templates_required_headcount_min"),
        sa.CheckConstraint("end_time > start_time", name="ck_coverage_templates_end_after_start"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coverage_templates_tenant_id", "coverage_templates", ["tenant_id"], unique=False)
    op.create_index("ix_coverage_templates_store_id", "coverage_templates", ["store_id"], unique=False)
    op.create_index(
        "ix_coverage_templates_tenant_id_store_id",
        "coverage_templates",
        ["tenant_id", "store_id"],
        unique=False,
    )
    op.create_index(
        "ix_coverage_templates_tenant_id_store_id_day_of_week",
        "coverage_templates",
        ["tenant_id", "store_id", "day_of_week"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_coverage_templates_tenant_id_store_id_day_of_week", table_name="coverage_templates")
    op.drop_index("ix_coverage_templates_tenant_id_store_id", table_name="coverage_templates")
    op.drop_index("ix_coverage_templates_store_id", table_name="coverage_templates")
    op.drop_index("ix_coverage_templates_tenant_id", table_name="coverage_templates")
    op.drop_table("coverage_templates")

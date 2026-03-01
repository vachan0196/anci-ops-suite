"""add hour targets table

Revision ID: 0010_hour_targets
Revises: 0009_availability_entries
Create Date: 2026-03-01 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010_hour_targets"
down_revision: Union[str, Sequence[str], None] = "0009_availability_entries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hour_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("min_hours", sa.Integer(), nullable=True),
        sa.Column("max_hours", sa.Integer(), nullable=True),
        sa.Column("target_hours", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hour_targets_tenant_id", "hour_targets", ["tenant_id"], unique=False)
    op.create_index("ix_hour_targets_user_id", "hour_targets", ["user_id"], unique=False)
    op.create_index("ix_hour_targets_store_id", "hour_targets", ["store_id"], unique=False)
    op.create_index("ix_hour_targets_week_start", "hour_targets", ["week_start"], unique=False)
    op.create_index("ix_hour_targets_tenant_id_user_id", "hour_targets", ["tenant_id", "user_id"], unique=False)
    op.create_index(
        "ix_hour_targets_tenant_id_week_start",
        "hour_targets",
        ["tenant_id", "week_start"],
        unique=False,
    )
    op.create_index(
        "uq_hour_targets_tenant_user_week_store_null",
        "hour_targets",
        ["tenant_id", "user_id", "week_start"],
        unique=True,
        postgresql_where=sa.text("store_id IS NULL"),
    )
    op.create_index(
        "uq_hour_targets_tenant_user_store_week_not_null",
        "hour_targets",
        ["tenant_id", "user_id", "store_id", "week_start"],
        unique=True,
        postgresql_where=sa.text("store_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_hour_targets_tenant_user_store_week_not_null", table_name="hour_targets")
    op.drop_index("uq_hour_targets_tenant_user_week_store_null", table_name="hour_targets")
    op.drop_index("ix_hour_targets_tenant_id_week_start", table_name="hour_targets")
    op.drop_index("ix_hour_targets_tenant_id_user_id", table_name="hour_targets")
    op.drop_index("ix_hour_targets_week_start", table_name="hour_targets")
    op.drop_index("ix_hour_targets_store_id", table_name="hour_targets")
    op.drop_index("ix_hour_targets_user_id", table_name="hour_targets")
    op.drop_index("ix_hour_targets_tenant_id", table_name="hour_targets")
    op.drop_table("hour_targets")

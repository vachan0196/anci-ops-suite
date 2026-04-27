"""add store opening hours and settings

Revision ID: 0017_store_opening_hours_settings
Revises: 0016_company_profile_fields
Create Date: 2026-04-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0017_store_opening_hours_settings"
down_revision: Union[str, Sequence[str], None] = "0016_company_profile_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_opening_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_store_opening_hours_day_of_week",
        ),
        sa.CheckConstraint(
            "is_closed OR (open_time IS NOT NULL AND close_time IS NOT NULL AND close_time > open_time)",
            name="ck_store_opening_hours_open_times",
        ),
        sa.UniqueConstraint("tenant_id", "store_id", "day_of_week", name="uq_store_opening_hours_tenant_store_day"),
    )
    op.create_index("ix_store_opening_hours_tenant_id", "store_opening_hours", ["tenant_id"], unique=False)
    op.create_index("ix_store_opening_hours_store_id", "store_opening_hours", ["store_id"], unique=False)
    op.create_index(
        "ix_store_opening_hours_tenant_id_store_id",
        "store_opening_hours",
        ["tenant_id", "store_id"],
        unique=False,
    )

    op.create_table(
        "store_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_week_start_day", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "business_week_start_day >= 0 AND business_week_start_day <= 6",
            name="ck_store_settings_business_week_start_day",
        ),
        sa.UniqueConstraint("tenant_id", "store_id", name="uq_store_settings_tenant_store"),
    )
    op.create_index("ix_store_settings_tenant_id", "store_settings", ["tenant_id"], unique=False)
    op.create_index("ix_store_settings_store_id", "store_settings", ["store_id"], unique=False)
    op.create_index(
        "ix_store_settings_tenant_id_store_id",
        "store_settings",
        ["tenant_id", "store_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_store_settings_tenant_id_store_id", table_name="store_settings")
    op.drop_index("ix_store_settings_store_id", table_name="store_settings")
    op.drop_index("ix_store_settings_tenant_id", table_name="store_settings")
    op.drop_table("store_settings")

    op.drop_index("ix_store_opening_hours_tenant_id_store_id", table_name="store_opening_hours")
    op.drop_index("ix_store_opening_hours_store_id", table_name="store_opening_hours")
    op.drop_index("ix_store_opening_hours_tenant_id", table_name="store_opening_hours")
    op.drop_table("store_opening_hours")

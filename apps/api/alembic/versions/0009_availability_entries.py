"""add availability entries table

Revision ID: 0009_availability_entries
Revises: 0008_shift_requests_swap_workflow
Create Date: 2026-03-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_availability_entries"
down_revision: Union[str, Sequence[str], None] = "0008_shift_requests_swap_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "availability_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_availability_entries_tenant_id", "availability_entries", ["tenant_id"], unique=False)
    op.create_index("ix_availability_entries_user_id", "availability_entries", ["user_id"], unique=False)
    op.create_index("ix_availability_entries_store_id", "availability_entries", ["store_id"], unique=False)
    op.create_index("ix_availability_entries_week_start", "availability_entries", ["week_start"], unique=False)
    op.create_index("ix_availability_entries_date", "availability_entries", ["date"], unique=False)
    op.create_index(
        "ix_availability_entries_tenant_id_user_id",
        "availability_entries",
        ["tenant_id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_availability_entries_tenant_id_week_start",
        "availability_entries",
        ["tenant_id", "week_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_availability_entries_tenant_id_week_start", table_name="availability_entries")
    op.drop_index("ix_availability_entries_tenant_id_user_id", table_name="availability_entries")
    op.drop_index("ix_availability_entries_date", table_name="availability_entries")
    op.drop_index("ix_availability_entries_week_start", table_name="availability_entries")
    op.drop_index("ix_availability_entries_store_id", table_name="availability_entries")
    op.drop_index("ix_availability_entries_user_id", table_name="availability_entries")
    op.drop_index("ix_availability_entries_tenant_id", table_name="availability_entries")
    op.drop_table("availability_entries")

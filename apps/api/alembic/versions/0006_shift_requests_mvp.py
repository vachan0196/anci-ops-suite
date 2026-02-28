"""add shift requests table

Revision ID: 0006_shift_requests_mvp
Revises: 0005_shifts_core
Create Date: 2026-02-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_shift_requests_mvp"
down_revision: Union[str, Sequence[str], None] = "0005_shifts_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shift_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shift_requests_tenant_id", "shift_requests", ["tenant_id"], unique=False)
    op.create_index("ix_shift_requests_shift_id", "shift_requests", ["shift_id"], unique=False)
    op.create_index("ix_shift_requests_requester_user_id", "shift_requests", ["requester_user_id"], unique=False)
    op.create_index(
        "ix_shift_requests_tenant_id_shift_id",
        "shift_requests",
        ["tenant_id", "shift_id"],
        unique=False,
    )
    op.create_index(
        "ix_shift_requests_tenant_id_requester_user_id",
        "shift_requests",
        ["tenant_id", "requester_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_shift_requests_tenant_id_status",
        "shift_requests",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_shift_requests_pending_per_requester_shift",
        "shift_requests",
        ["tenant_id", "shift_id", "requester_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_shift_requests_pending_per_requester_shift", table_name="shift_requests")
    op.drop_index("ix_shift_requests_tenant_id_status", table_name="shift_requests")
    op.drop_index("ix_shift_requests_tenant_id_requester_user_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_tenant_id_shift_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_requester_user_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_shift_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_tenant_id", table_name="shift_requests")
    op.drop_table("shift_requests")

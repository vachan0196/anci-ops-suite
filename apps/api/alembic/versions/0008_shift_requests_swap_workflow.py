"""add swap workflow fields for shift requests

Revision ID: 0008_shift_requests_swap_workflow
Revises: 0007_shifts_publish_state
Create Date: 2026-02-28 00:00:02.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_shift_requests_swap_workflow"
down_revision: Union[str, Sequence[str], None] = "0007_shifts_publish_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shift_requests",
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shift_requests_target_user_id_users",
        "shift_requests",
        "users",
        ["target_user_id"],
        ["id"],
    )
    op.create_index("ix_shift_requests_target_user_id", "shift_requests", ["target_user_id"], unique=False)
    op.create_index(
        "ix_shift_requests_tenant_id_target_user_id",
        "shift_requests",
        ["tenant_id", "target_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_shift_requests_pending_target_per_requester_shift",
        "shift_requests",
        ["tenant_id", "shift_id", "requester_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending_target'"),
    )


def downgrade() -> None:
    op.drop_index("uq_shift_requests_pending_target_per_requester_shift", table_name="shift_requests")
    op.drop_index("ix_shift_requests_tenant_id_target_user_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_target_user_id", table_name="shift_requests")
    op.drop_constraint("fk_shift_requests_target_user_id_users", "shift_requests", type_="foreignkey")
    op.drop_column("shift_requests", "target_user_id")

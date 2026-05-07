"""phase p4 swap target shift

Revision ID: 0021_phase_p4_swap_target_shift
Revises: 0020_employee_request_workflows
Create Date: 2026-05-05 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0021_phase_p4_swap_target_shift"
down_revision: Union[str, Sequence[str], None] = "0020_employee_request_workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shift_requests",
        sa.Column("target_shift_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shift_requests_target_shift_id_shifts",
        "shift_requests",
        "shifts",
        ["target_shift_id"],
        ["id"],
    )
    op.create_index("ix_shift_requests_target_shift_id", "shift_requests", ["target_shift_id"], unique=False)
    op.create_index(
        "ix_shift_requests_tenant_id_target_shift_id",
        "shift_requests",
        ["tenant_id", "target_shift_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shift_requests_tenant_id_target_shift_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_target_shift_id", table_name="shift_requests")
    op.drop_constraint("fk_shift_requests_target_shift_id_shifts", "shift_requests", type_="foreignkey")
    op.drop_column("shift_requests", "target_shift_id")

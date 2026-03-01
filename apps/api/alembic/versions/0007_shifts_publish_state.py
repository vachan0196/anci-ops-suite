"""add shifts publish state columns

Revision ID: 0007_shifts_publish_state
Revises: 0006_shift_requests_mvp
Create Date: 2026-02-28 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_shifts_publish_state"
down_revision: Union[str, Sequence[str], None] = "0006_shift_requests_mvp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shifts", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shifts", sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_shifts_published_by_user_id_users",
        "shifts",
        "users",
        ["published_by_user_id"],
        ["id"],
    )
    op.create_index("ix_shifts_published_by_user_id", "shifts", ["published_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shifts_published_by_user_id", table_name="shifts")
    op.drop_constraint("fk_shifts_published_by_user_id_users", "shifts", type_="foreignkey")
    op.drop_column("shifts", "published_by_user_id")
    op.drop_column("shifts", "published_at")

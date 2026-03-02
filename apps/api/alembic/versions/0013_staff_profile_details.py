"""add staff profile details fields

Revision ID: 0013_staff_profile_details
Revises: 0012_store_details
Create Date: 2026-03-02 00:00:02.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013_staff_profile_details"
down_revision: Union[str, Sequence[str], None] = "0012_store_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("staff_profiles", sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True))
    op.add_column("staff_profiles", sa.Column("pay_type", sa.Text(), nullable=True))
    op.add_column("staff_profiles", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("staff_profiles", sa.Column("emergency_contact_name", sa.Text(), nullable=True))
    op.add_column("staff_profiles", sa.Column("emergency_contact_phone", sa.Text(), nullable=True))
    op.add_column("staff_profiles", sa.Column("contract_type", sa.Text(), nullable=True))
    op.add_column("staff_profiles", sa.Column("rtw_status", sa.Text(), nullable=True))
    op.add_column("staff_profiles", sa.Column("rtw_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("staff_profiles", sa.Column("rtw_checked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("staff_profiles", sa.Column("notes", sa.Text(), nullable=True))

    op.create_foreign_key(
        "fk_staff_profiles_rtw_checked_by_user_id_users",
        "staff_profiles",
        "users",
        ["rtw_checked_by_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_staff_profiles_rtw_checked_by_user_id",
        "staff_profiles",
        ["rtw_checked_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_staff_profiles_rtw_checked_by_user_id", table_name="staff_profiles")
    op.drop_constraint("fk_staff_profiles_rtw_checked_by_user_id_users", "staff_profiles", type_="foreignkey")

    op.drop_column("staff_profiles", "notes")
    op.drop_column("staff_profiles", "rtw_checked_by_user_id")
    op.drop_column("staff_profiles", "rtw_checked_at")
    op.drop_column("staff_profiles", "rtw_status")
    op.drop_column("staff_profiles", "contract_type")
    op.drop_column("staff_profiles", "emergency_contact_phone")
    op.drop_column("staff_profiles", "emergency_contact_name")
    op.drop_column("staff_profiles", "phone")
    op.drop_column("staff_profiles", "pay_type")
    op.drop_column("staff_profiles", "hourly_rate")

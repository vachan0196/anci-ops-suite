"""add company profile fields to tenants

Revision ID: 0016_company_profile_fields
Revises: 0015_staff_roles_and_shift_overrides
Create Date: 2026-04-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0016_company_profile_fields"
down_revision: Union[str, Sequence[str], None] = "0015_staff_roles_and_shift_overrides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("company_name", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("owner_name", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("business_email", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("phone_number", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("registered_address", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "company_setup_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("company_setup_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "company_setup_completed_at")
    op.drop_column("tenants", "company_setup_completed")
    op.drop_column("tenants", "registered_address")
    op.drop_column("tenants", "phone_number")
    op.drop_column("tenants", "business_email")
    op.drop_column("tenants", "owner_name")
    op.drop_column("tenants", "company_name")

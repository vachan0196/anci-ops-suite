"""staff rules soft caps

Revision ID: 0031_staff_rules_soft_caps
Revises: 0030_phase_q5_2a_step_up_auth
Create Date: 2026-06-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0031_staff_rules_soft_caps"
down_revision: str | None = "0030_phase_q5_2a_step_up_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "staff_profiles",
        sa.Column("weekly_working_hour_soft_cap", sa.Numeric(6, 2), nullable=True),
    )
    op.add_column(
        "staff_profiles",
        sa.Column("monthly_working_hour_soft_cap", sa.Numeric(6, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("staff_profiles", "monthly_working_hour_soft_cap")
    op.drop_column("staff_profiles", "weekly_working_hour_soft_cap")

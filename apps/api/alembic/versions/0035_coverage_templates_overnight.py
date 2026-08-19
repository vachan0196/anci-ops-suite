"""allow overnight coverage template windows

Revision ID: 0035_coverage_templates_overnight
Revises: 0034_coverage_1a_provenance
Create Date: 2026-08-18
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0035_coverage_templates_overnight"
down_revision: str | None = "0034_coverage_1a_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_coverage_templates_end_after_start",
        "coverage_templates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coverage_templates_start_end_different",
        "coverage_templates",
        "end_time <> start_time",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_coverage_templates_start_end_different",
        "coverage_templates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coverage_templates_end_after_start",
        "coverage_templates",
        "end_time > start_time",
    )

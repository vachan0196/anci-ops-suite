"""add store email and notes

Revision ID: 0032_store_email_notes
Revises: 0031_staff_rules_soft_caps
Create Date: 2026-06-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0032_store_email_notes"
down_revision: str | None = "0031_staff_rules_soft_caps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("stores", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "notes")
    op.drop_column("stores", "email")

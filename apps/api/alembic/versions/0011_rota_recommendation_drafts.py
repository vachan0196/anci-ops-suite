"""add rota recommendation draft tables

Revision ID: 0011_rota_recommendation_drafts
Revises: 0010_hour_targets
Create Date: 2026-03-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011_rota_recommendation_drafts"
down_revision: Union[str, Sequence[str], None] = "0010_hour_targets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rota_recommendation_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rota_recommendation_drafts_tenant_id", "rota_recommendation_drafts", ["tenant_id"], unique=False)
    op.create_index("ix_rota_recommendation_drafts_store_id", "rota_recommendation_drafts", ["store_id"], unique=False)
    op.create_index("ix_rota_recommendation_drafts_week_start", "rota_recommendation_drafts", ["week_start"], unique=False)
    op.create_index(
        "ix_rota_recommendation_drafts_tenant_id_store_id",
        "rota_recommendation_drafts",
        ["tenant_id", "store_id"],
        unique=False,
    )
    op.create_index(
        "ix_rota_recommendation_drafts_tenant_id_week_start",
        "rota_recommendation_drafts",
        ["tenant_id", "week_start"],
        unique=False,
    )
    op.create_index(
        "uq_rota_recommendation_drafts_active_per_store_week",
        "rota_recommendation_drafts",
        ["tenant_id", "store_id", "week_start"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )

    op.create_table(
        "rota_recommendation_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["rota_recommendation_drafts.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.ForeignKeyConstraint(["proposed_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rota_recommendation_items_tenant_id", "rota_recommendation_items", ["tenant_id"], unique=False)
    op.create_index("ix_rota_recommendation_items_draft_id", "rota_recommendation_items", ["draft_id"], unique=False)
    op.create_index("ix_rota_recommendation_items_shift_id", "rota_recommendation_items", ["shift_id"], unique=False)
    op.create_index(
        "ix_rota_recommendation_items_tenant_id_draft_id",
        "rota_recommendation_items",
        ["tenant_id", "draft_id"],
        unique=False,
    )
    op.create_index(
        "uq_rota_recommendation_items_draft_shift",
        "rota_recommendation_items",
        ["draft_id", "shift_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_rota_recommendation_items_draft_shift", table_name="rota_recommendation_items")
    op.drop_index("ix_rota_recommendation_items_tenant_id_draft_id", table_name="rota_recommendation_items")
    op.drop_index("ix_rota_recommendation_items_shift_id", table_name="rota_recommendation_items")
    op.drop_index("ix_rota_recommendation_items_draft_id", table_name="rota_recommendation_items")
    op.drop_index("ix_rota_recommendation_items_tenant_id", table_name="rota_recommendation_items")
    op.drop_table("rota_recommendation_items")

    op.drop_index("uq_rota_recommendation_drafts_active_per_store_week", table_name="rota_recommendation_drafts")
    op.drop_index("ix_rota_recommendation_drafts_tenant_id_week_start", table_name="rota_recommendation_drafts")
    op.drop_index("ix_rota_recommendation_drafts_tenant_id_store_id", table_name="rota_recommendation_drafts")
    op.drop_index("ix_rota_recommendation_drafts_week_start", table_name="rota_recommendation_drafts")
    op.drop_index("ix_rota_recommendation_drafts_store_id", table_name="rota_recommendation_drafts")
    op.drop_index("ix_rota_recommendation_drafts_tenant_id", table_name="rota_recommendation_drafts")
    op.drop_table("rota_recommendation_drafts")

"""coverage 1a work areas and generation provenance

Revision ID: 0034_coverage_1a_provenance
Revises: 0033_admin_staff_availability_week
Create Date: 2026-07-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0034_coverage_1a_provenance"
down_revision: str | None = "0033_admin_staff_availability_week"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_work_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_site_work_areas_tenant_id_store_id",
        "site_work_areas",
        ["tenant_id", "store_id"],
        unique=False,
    )
    op.create_index("ix_site_work_areas_tenant_id", "site_work_areas", ["tenant_id"], unique=False)
    op.create_index("ix_site_work_areas_store_id", "site_work_areas", ["store_id"], unique=False)
    op.create_index(
        "uq_site_work_areas_active_label",
        "site_work_areas",
        ["tenant_id", "store_id", sa.text("lower(label)")],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.add_column(
        "coverage_templates",
        sa.Column("work_area_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "coverage_templates",
        sa.Column("display_label", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_coverage_templates_work_area_id_site_work_areas",
        "coverage_templates",
        "site_work_areas",
        ["work_area_id"],
        ["id"],
    )
    op.create_index(
        "ix_coverage_templates_work_area_id",
        "coverage_templates",
        ["work_area_id"],
        unique=False,
    )

    op.create_table(
        "generation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'completed'"), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("replaced_count", sa.Integer(), nullable=False),
        sa.Column("kept_matching_count", sa.Integer(), nullable=False),
        sa.Column("kept_conflict_count", sa.Integer(), nullable=False),
        sa.Column("generated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('completed')", name="ck_generation_runs_status"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generation_runs_tenant_store_week",
        "generation_runs",
        ["tenant_id", "store_id", "week_start"],
        unique=False,
    )
    op.create_index("ix_generation_runs_tenant_id", "generation_runs", ["tenant_id"], unique=False)
    op.create_index("ix_generation_runs_store_id", "generation_runs", ["store_id"], unique=False)
    op.create_index("ix_generation_runs_week_start", "generation_runs", ["week_start"], unique=False)
    op.create_index(
        "ix_generation_runs_generated_by_user_id",
        "generation_runs",
        ["generated_by_user_id"],
        unique=False,
    )

    op.add_column("shifts", sa.Column("source", sa.String(length=32), nullable=True))
    op.execute("UPDATE shifts SET source = 'legacy_untracked'")
    op.alter_column(
        "shifts",
        "source",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default=sa.text("'manual'"),
    )
    op.add_column(
        "shifts",
        sa.Column("generation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "shifts",
        sa.Column("source_coverage_template_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "shifts",
        sa.Column("work_area_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("shifts", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "shifts",
        sa.Column("superseded_by_generation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shifts_generation_run_id_generation_runs",
        "shifts",
        "generation_runs",
        ["generation_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_shifts_source_coverage_template_id_coverage_templates",
        "shifts",
        "coverage_templates",
        ["source_coverage_template_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_shifts_work_area_id_site_work_areas",
        "shifts",
        "site_work_areas",
        ["work_area_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_shifts_superseded_by_generation_run_id_generation_runs",
        "shifts",
        "generation_runs",
        ["superseded_by_generation_run_id"],
        ["id"],
    )
    op.create_index("ix_shifts_generation_run_id", "shifts", ["generation_run_id"], unique=False)
    op.create_index(
        "ix_shifts_source_coverage_template_id",
        "shifts",
        ["source_coverage_template_id"],
        unique=False,
    )
    op.create_index("ix_shifts_work_area_id", "shifts", ["work_area_id"], unique=False)
    op.create_index(
        "ix_shifts_superseded_by_generation_run_id",
        "shifts",
        ["superseded_by_generation_run_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_shifts_source",
        "shifts",
        "source IN ('manual', 'demand_generation', 'legacy_untracked')",
    )
    op.create_check_constraint(
        "ck_shifts_supersession_pair",
        "shifts",
        "(superseded_at IS NULL AND superseded_by_generation_run_id IS NULL) "
        "OR (superseded_at IS NOT NULL AND superseded_by_generation_run_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_shifts_superseded_status",
        "shifts",
        "superseded_at IS NULL OR status = 'cancelled'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_shifts_superseded_status", "shifts", type_="check")
    op.drop_constraint("ck_shifts_supersession_pair", "shifts", type_="check")
    op.drop_constraint("ck_shifts_source", "shifts", type_="check")
    op.drop_index("ix_shifts_superseded_by_generation_run_id", table_name="shifts")
    op.drop_index("ix_shifts_work_area_id", table_name="shifts")
    op.drop_index("ix_shifts_source_coverage_template_id", table_name="shifts")
    op.drop_index("ix_shifts_generation_run_id", table_name="shifts")
    op.drop_constraint(
        "fk_shifts_superseded_by_generation_run_id_generation_runs",
        "shifts",
        type_="foreignkey",
    )
    op.drop_constraint("fk_shifts_work_area_id_site_work_areas", "shifts", type_="foreignkey")
    op.drop_constraint(
        "fk_shifts_source_coverage_template_id_coverage_templates",
        "shifts",
        type_="foreignkey",
    )
    op.drop_constraint("fk_shifts_generation_run_id_generation_runs", "shifts", type_="foreignkey")
    op.drop_column("shifts", "superseded_by_generation_run_id")
    op.drop_column("shifts", "superseded_at")
    op.drop_column("shifts", "work_area_id")
    op.drop_column("shifts", "source_coverage_template_id")
    op.drop_column("shifts", "generation_run_id")
    op.drop_column("shifts", "source")

    op.drop_index("ix_generation_runs_generated_by_user_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_week_start", table_name="generation_runs")
    op.drop_index("ix_generation_runs_store_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_tenant_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_tenant_store_week", table_name="generation_runs")
    op.drop_table("generation_runs")

    op.drop_index("ix_coverage_templates_work_area_id", table_name="coverage_templates")
    op.drop_constraint(
        "fk_coverage_templates_work_area_id_site_work_areas",
        "coverage_templates",
        type_="foreignkey",
    )
    op.drop_column("coverage_templates", "display_label")
    op.drop_column("coverage_templates", "work_area_id")

    op.drop_index("uq_site_work_areas_active_label", table_name="site_work_areas")
    op.drop_index("ix_site_work_areas_store_id", table_name="site_work_areas")
    op.drop_index("ix_site_work_areas_tenant_id", table_name="site_work_areas")
    op.drop_index("ix_site_work_areas_tenant_id_store_id", table_name="site_work_areas")
    op.drop_table("site_work_areas")

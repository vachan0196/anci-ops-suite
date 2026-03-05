"""add staff roles and shift override tracking

Revision ID: 0015_staff_roles_and_shift_overrides
Revises: 0014_coverage_templates
Create Date: 2026-03-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0015_staff_roles_and_shift_overrides"
down_revision: Union[str, Sequence[str], None] = "0014_coverage_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "staff_id", "role", name="uq_staff_roles_tenant_staff_role"),
    )
    op.create_index("ix_staff_roles_tenant_id", "staff_roles", ["tenant_id"], unique=False)
    op.create_index("ix_staff_roles_staff_id", "staff_roles", ["staff_id"], unique=False)
    op.create_index("ix_staff_roles_tenant_id_staff_id", "staff_roles", ["tenant_id", "staff_id"], unique=False)
    op.create_index("ix_staff_roles_tenant_id_role", "staff_roles", ["tenant_id", "role"], unique=False)

    op.add_column("shifts", sa.Column("required_role", sa.Text(), nullable=True))
    op.add_column("shifts", sa.Column("role_override", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column(
        "shifts",
        sa.Column("availability_override", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("shifts", sa.Column("overridden_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("shifts", sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shifts", sa.Column("override_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_shifts_overridden_by_user_id_users",
        "shifts",
        "users",
        ["overridden_by_user_id"],
        ["id"],
    )
    op.create_index("ix_shifts_overridden_by_user_id", "shifts", ["overridden_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shifts_overridden_by_user_id", table_name="shifts")
    op.drop_constraint("fk_shifts_overridden_by_user_id_users", "shifts", type_="foreignkey")
    op.drop_column("shifts", "override_reason")
    op.drop_column("shifts", "overridden_at")
    op.drop_column("shifts", "overridden_by_user_id")
    op.drop_column("shifts", "availability_override")
    op.drop_column("shifts", "role_override")
    op.drop_column("shifts", "required_role")

    op.drop_index("ix_staff_roles_tenant_id_role", table_name="staff_roles")
    op.drop_index("ix_staff_roles_tenant_id_staff_id", table_name="staff_roles")
    op.drop_index("ix_staff_roles_staff_id", table_name="staff_roles")
    op.drop_index("ix_staff_roles_tenant_id", table_name="staff_roles")
    op.drop_table("staff_roles")

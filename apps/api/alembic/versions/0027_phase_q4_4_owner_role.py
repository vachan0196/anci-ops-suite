"""phase q4 4 owner role

Revision ID: 0027_phase_q4_4_owner_role
Revises: 0026_phase_q4_3_email_verified_at
Create Date: 2026-05-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0027_phase_q4_4_owner_role"
down_revision: Union[str, Sequence[str], None] = "0026_phase_q4_3_email_verified_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


metadata = sa.MetaData()
tenants = sa.Table(
    "tenants",
    metadata,
    sa.Column("id", sa.UUID(), primary_key=True),
)
users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
tenant_users = sa.Table(
    "tenant_users",
    metadata,
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("tenant_id", sa.UUID(), nullable=False),
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("role", sa.String(length=32), nullable=False),
)


def _backfill_one_owner_per_tenant(connection: sa.engine.Connection) -> None:
    tenant_ids = connection.execute(sa.select(tenants.c.id)).scalars().all()

    for tenant_id in tenant_ids:
        owner_exists = connection.execute(
            sa.select(tenant_users.c.id)
            .where(
                tenant_users.c.tenant_id == tenant_id,
                tenant_users.c.role == "owner",
            )
            .limit(1)
        ).first()
        if owner_exists is not None:
            continue

        candidate_id = connection.execute(
            sa.select(tenant_users.c.id)
            .join(users, users.c.id == tenant_users.c.user_id)
            .where(
                tenant_users.c.tenant_id == tenant_id,
                tenant_users.c.role == "admin",
            )
            .order_by(users.c.created_at.asc(), tenant_users.c.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if candidate_id is None:
            candidate_id = connection.execute(
                sa.select(tenant_users.c.id)
                .join(users, users.c.id == tenant_users.c.user_id)
                .where(tenant_users.c.tenant_id == tenant_id)
                .order_by(users.c.created_at.asc(), tenant_users.c.id.asc())
                .limit(1)
            ).scalar_one_or_none()

        if candidate_id is None:
            continue

        connection.execute(
            tenant_users.update()
            .where(tenant_users.c.id == candidate_id)
            .values(role="owner")
        )


def upgrade() -> None:
    # tenant_users.role has no database CHECK constraint in the current schema.
    _backfill_one_owner_per_tenant(op.get_bind())


def downgrade() -> None:
    op.execute("UPDATE tenant_users SET role = 'admin' WHERE role = 'owner'")

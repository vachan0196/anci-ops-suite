"""add store details fields

Revision ID: 0012_store_details
Revises: 0011_rota_recommendation_drafts
Create Date: 2026-03-02 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012_store_details"
down_revision: Union[str, Sequence[str], None] = "0011_rota_recommendation_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("address_line1", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("city", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("postcode", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("manager_user_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_foreign_key(
        "fk_stores_manager_user_id_users",
        "stores",
        "users",
        ["manager_user_id"],
        ["id"],
    )
    op.create_index("ix_stores_manager_user_id", "stores", ["manager_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stores_manager_user_id", table_name="stores")
    op.drop_constraint("fk_stores_manager_user_id_users", "stores", type_="foreignkey")

    op.drop_column("stores", "manager_user_id")
    op.drop_column("stores", "phone")
    op.drop_column("stores", "postcode")
    op.drop_column("stores", "city")
    op.drop_column("stores", "address_line1")

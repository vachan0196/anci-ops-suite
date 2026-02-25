"""create hot_food_demand_inputs table

Revision ID: 0001_hot_food
Revises: 
Create Date: 2026-02-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_hot_food"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hot_food_demand_inputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.String(length=255), nullable=False),
        sa.Column("item_id", sa.String(length=255), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("units_sold", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hot_food_demand_inputs_id",
        "hot_food_demand_inputs",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_hot_food_demand_inputs_item_id",
        "hot_food_demand_inputs",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "ix_hot_food_demand_inputs_store_id",
        "hot_food_demand_inputs",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_hot_food_demand_inputs_ts",
        "hot_food_demand_inputs",
        ["ts"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hot_food_demand_inputs_ts", table_name="hot_food_demand_inputs")
    op.drop_index("ix_hot_food_demand_inputs_store_id", table_name="hot_food_demand_inputs")
    op.drop_index("ix_hot_food_demand_inputs_item_id", table_name="hot_food_demand_inputs")
    op.drop_index("ix_hot_food_demand_inputs_id", table_name="hot_food_demand_inputs")
    op.drop_table("hot_food_demand_inputs")

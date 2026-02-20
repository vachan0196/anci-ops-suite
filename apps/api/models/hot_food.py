from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base


class HotFoodDemandInput(Base):
    __tablename__ = "hot_food_demand_inputs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    store_id: Mapped[str] = mapped_column(String(255), index=True)
    item_id: Mapped[str] = mapped_column(String(255), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    units_sold: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
    )

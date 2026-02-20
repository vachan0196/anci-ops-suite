from datetime import datetime

from pydantic import BaseModel


class HotFoodDemandIn(BaseModel):
    store_id: str
    item_id: str
    ts: datetime
    units_sold: int


class HotFoodDemandOut(HotFoodDemandIn):
    id: int

    model_config = {"from_attributes": True}

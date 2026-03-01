import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict

AvailabilityType = Literal["unavailable", "preferred_off", "available_extra", "available"]


class AvailabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID | None = None
    week_start: date
    date: date
    start_time: time | None = None
    end_time: time | None = None
    type: AvailabilityType
    notes: str | None = None


class AvailabilityRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    store_id: uuid.UUID | None
    week_start: date
    date: date
    start_time: time | None
    end_time: time | None
    type: AvailabilityType
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

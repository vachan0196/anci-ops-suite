import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AvailabilityType = Literal["unavailable", "preferred_off", "available_extra", "available"]


class AvailabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID | None = None
    week_start: date
    date: date
    start_time: time | None = None
    end_time: time | None = None
    type: AvailabilityType
    notes: str | None = Field(default=None, max_length=500)


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
    source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminStaffAvailabilityWeekEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    start_time: time | None = None
    end_time: time | None = None
    type: AvailabilityType
    notes: str | None = Field(default=None, max_length=500)


class AdminStaffAvailabilityWeekReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date
    entries: list[AdminStaffAvailabilityWeekEntry] = Field(default_factory=list, max_length=64)


class AdminStaffAvailabilityWeekRead(BaseModel):
    staff_user_id: uuid.UUID
    week_start: date
    items: list[AvailabilityRead] = Field(default_factory=list)
